"""Deterministic grid planning and permutation GA; no UI or server dependencies."""
from __future__ import annotations
from dataclasses import dataclass
from heapq import heappop, heappush
import math
import random
from collections import OrderedDict
from typing import Callable
import numpy as np
from scipy.ndimage import maximum_filter


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, float(x)))))


@dataclass(frozen=True)
class Order:
    id: str
    x: int
    y: int
    importance: float = 5
    waited: float = 0       # seconds already waiting
    patience: float = 300   # desired arrival within seconds of ordering
    risk: float = .5        # consequence/risk multiplier, not calibrated probability
    speed: float = .8       # m/s around destination
    service: float = 10     # seconds
    forbidden: tuple[int, ...] = ()  # 1-based delivery positions


class Costmap:
    """White is free. Gray adds traversal cost; <= threshold is blocked.

    Square inflation conservatively covers a circular footprint. Diagonals may
    not cut corners. Pixel coordinates refer to cell centers, origin top-left.
    """
    def __init__(self, pixels, resolution=.1, threshold=100, radius=.2, gray_cost=2):
        a = np.asarray(pixels, dtype=np.uint8)
        if a.ndim != 2 or min(a.shape) < 4 or max(a.shape) > 512:
            raise ValueError('地圖需為 4–512 px 的灰階圖片；請先縮小較大的地圖。')
        self.pixels = a
        self.resolution = resolution
        self.height, self.width = a.shape
        blocked = a <= threshold
        # Outside the image is occupied too.
        blocked = blocked.copy()
        blocked[[0, -1], :] = True
        blocked[:, [0, -1]] = True
        r = math.ceil(radius / resolution)
        self.blocked = maximum_filter(blocked, size=2*r+1, mode='constant', cval=1)
        self.cost = 1 + gray_cost * (255-a.astype(float))/255

    def valid(self, p):
        x, y = p
        return 0 <= x < self.width and 0 <= y < self.height and not self.blocked[y, x]

    def astar(self, start, goal, cancelled=lambda: False):
        if not self.valid(start) or not self.valid(goal):
            raise ValueError(f'節點 {start} 或 {goal} 位於牆壁、地圖外或機器人安全邊界。')
        def heuristic(p):
            dx, dy = abs(p[0]-goal[0]), abs(p[1]-goal[1])
            return max(dx, dy)+(math.sqrt(2)-1)*min(dx, dy)
        heap = [(heuristic(start), 0., start)]
        best = {start: 0.}
        previous = {}
        visits = 0
        while heap:
            _, g, p = heappop(heap)
            if g > best[p]:
                continue
            if p == goal:
                path = [p]
                while p != start:
                    p = previous[p]
                    path.append(p)
                path.reverse()
                distance = sum(math.hypot(b[0]-a[0], b[1]-a[1]) for a,b in zip(path,path[1:]))*self.resolution
                return path, distance, g*self.resolution
            visits += 1
            if visits % 1024 == 0 and cancelled():
                raise InterruptedError('已停止規劃')
            x,y = p
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                q = (x+dx, y+dy)
                if not self.valid(q):
                    continue
                if dx and dy and (not self.valid((x+dx,y)) or not self.valid((x,y+dy))):
                    continue
                ng = g + math.hypot(dx,dy)*(self.cost[y,x]+self.cost[q[1],q[0]])/2
                if ng < best.get(q, math.inf):
                    best[q] = ng
                    previous[q] = p
                    heappush(heap,(ng+heuristic(q),ng,q))
        raise ValueError(f'節點 {start} → {goal} 不可達；請檢查門口寬度與機器人半徑。')


def prepare(grid, orders, start, end=None, cruise=.8, local_radius=1., progress=None, cancelled=lambda: False):
    points = [tuple(start)]+[(o.x,o.y) for o in orders]
    if end is not None:
        points.append(tuple(end))
    for i,p in enumerate(points):
        if not grid.valid(p):
            label = '起點' if i==0 else (orders[i-1].id if i<=len(orders) else '終點')
            raise ValueError(f'{label} {p} 位於牆壁或膨脹安全區，請重新標記。')
    n = len(points)
    distance = np.zeros((n,n)); effort = distance.copy(); travel = distance.copy()
    paths = {}
    total = n*(n-1)//2; done=0
    for i in range(n):
        paths[f'{i}:{i}'] = [points[i]]
        for j in range(i+1,n):
            if cancelled(): raise InterruptedError('已停止規劃')
            path,d,c = grid.astar(points[i],points[j],cancelled)
            paths[f'{i}:{j}']=path; paths[f'{j}:{i}']=path[::-1]
            distance[i,j]=distance[j,i]=d
            effort[i,j]=effort[j,i]=c
            done+=1
            if progress: progress(done,total)
    # Destination-local speed applies only inside its Euclidean neighborhood.
    # Gray pixels model increased traversal time along the complete path.
    for i in range(n):
        for j in range(n):
            path=paths[f'{i}:{j}']; t=0.
            for a,b in zip(path,path[1:]):
                ds=math.hypot(b[0]-a[0],b[1]-a[1])*grid.resolution
                cost=(grid.cost[a[1],a[0]]+grid.cost[b[1],b[0]])/2
                near=math.hypot((a[0]+b[0])/2-points[j][0],(a[1]+b[1])/2-points[j][1])*grid.resolution <= local_radius
                speed=min(cruise,orders[j-1].speed) if 1<=j<=len(orders) and near else cruise
                t+=ds*cost/speed
            travel[i,j]=t
    return {'points':points,'distance':distance,'effort':effort,'travel':travel,'paths':paths}


DEFAULT_COEFFICIENTS={'importance':2.,'wait':2.,'risk':2.,'distance':1.,'slow':1.,'bias':-3.}


def weights(orders, matrix, cruise, coefficients=None):
    c = dict(DEFAULT_COEFFICIENTS, **(coefficients or {}))
    rows=[]
    for j,o in enumerate(orders,1):
        features=[o.importance/10, min(o.waited/o.patience,3),o.risk,
                  min(matrix['distance'][0,j]/50,3),max(0,1-min(o.speed,cruise)/cruise)]
        z=c['bias']+sum(c[k]*v for k,v in zip(('importance','wait','risk','distance','slow'),features))
        rows.append({'id':o.id,'features':features,'z':z,'weight':1+9*sigmoid(z)})
    return rows


class Objective:
    def __init__(self,orders,matrix,rows,return_to_start=True,custom_end=False,priority=1.,risk_penalty=120.,distance_penalty=1.,mode='operational'):
        self.orders=orders; self.m=matrix; self.rows=rows
        self.return_to_start=return_to_start; self.custom_end=custom_end
        self.priority=priority; self.risk_penalty=risk_penalty; self.distance_penalty=distance_penalty;self.mode=mode
        self.cache=OrderedDict()

    def evaluate(self,route,details=False):
        if not details and route in self.cache: return self.cache[route]
        t=0.; distance=0.; weighted_arrival=0.; risk=0.; legacy=0.; previous=0; schedule=[]
        for position,index in enumerate(route,1):
            o=self.orders[index]; node=index+1
            if position in o.forbidden:
                return math.inf if not details else {'loss':math.inf}
            d=float(self.m['distance'][previous,node]); dt=float(self.m['travel'][previous,node])
            t+=dt; distance+=d; w=self.rows[index]['weight']
            weighted_arrival+=w*t
            lateness=max(0.,o.waited+t-o.patience)
            risk+=o.risk*lateness/o.patience
            wi=0 if previous==0 else self.rows[previous-1]['weight']
            legacy+=sigmoid(d/(10*position*(1+wi+w)))
            schedule.append({'id':o.id,'node':node,'position':position,'arrival':t,'wait_total':o.waited+t,'late':lateness,'weight':w,'distance':d,'travel':dt,'service':o.service})
            t+=o.service; previous=node
        last=len(self.orders)+1 if self.custom_end else (0 if self.return_to_start else None)
        if last is not None:
            d=float(self.m['distance'][previous,last]); distance+=d
            t+=float(self.m['travel'][previous,last])
            wi=self.rows[previous-1]['weight']
            legacy+=sigmoid(d/(10*(len(route)+1)*(1+wi)))
        avg=weighted_arrival/sum(r['weight'] for r in self.rows)
        loss=legacy if self.mode=='disclosure' else t+self.priority*avg+self.risk_penalty*risk+self.distance_penalty*distance
        if details:
            return {'loss':loss,'duration':t,'distance':distance,'weighted_arrival':avg,'risk_cost':risk,'schedule':schedule,'route':[0]+[i+1 for i in route]+([] if last is None else [last])}
        self.cache[route]=loss
        if len(self.cache)>50000: self.cache.popitem(last=False)
        return loss


def repair(route, orders, rng):
    """Bipartite matching ensures all positional constraints or proves impossible."""
    if all(i+1 not in orders[g].forbidden for i,g in enumerate(route)): return tuple(route)
    match={}; preferred={g:i for i,g in enumerate(route)}
    def assign(g,seen):
        positions=list(range(len(route)))
        rng.shuffle(positions)
        positions.sort(key=lambda p:p!=preferred[g])
        for p in positions:
            if p in seen or p+1 in orders[g].forbidden: continue
            seen.add(p)
            if p not in match or assign(match[p],seen):
                match[p]=g; return True
        return False
    for g in sorted(route,key=lambda g:len(orders[g].forbidden),reverse=True):
        if not assign(g,set()): raise ValueError('順位限制互相衝突：不存在能配送全部訂單的排列。')
    return tuple(match[p] for p in range(len(route)))


def pmx(a,b,rng):
    n=len(a)
    if n<2: return tuple(a)
    left,right=sorted(rng.sample(range(n+1),2))
    child=[None]*n; child[left:right]=a[left:right]
    for i in range(left,right):
        if b[i] in child: continue
        pos=i
        while left<=pos<right: pos=b.index(a[pos])
        child[pos]=b[i]
    return tuple(b[i] if v is None else v for i,v in enumerate(child))


def evolve(objective,population=60,generations=80,worlds=4,sower=True,interval=10,migration=.15,mutation=.2,seed=42,callback=None,cancelled=lambda:False):
    n=len(objective.orders)
    if not n: raise ValueError('請至少新增一筆訂單。')
    count=worlds if sower else 1
    rngs=[random.Random(seed+104729*i) for i in range(count)]
    original=tuple(range(n))
    pops=[]
    for rng in rngs:
        pops.append([repair(tuple(rng.sample(range(n),n)),objective.orders,rng) for _ in range(population)])
    # Same baseline in all worlds makes on/off comparisons reproducible.
    baseline=repair(original,objective.orders,random.Random(seed))
    for pop in pops: pop[0]=baseline
    history=[]; events=[]
    for gen in range(generations+1):
        if cancelled(): raise InterruptedError('已停止規劃')
        for pop in pops: pop.sort(key=objective.evaluate)
        migrated=0
        if sower and count>1 and gen>0 and gen%interval==0 and migration>0:
            k=min(population-1,max(1,int(population*migration)))
            # Harvest each world's best, shuffle, distribute to OTHER worlds.
            pool=[(w,tuple(r)) for w,pop in enumerate(pops) for r in pop[:k]]
            rngs[0].shuffle(pool)
            for w,pop in enumerate(pops):
                incoming=[r for source,r in pool if source!=w][:k]
                pop[-len(incoming):]=incoming
                migrated+=len(incoming)
                pop.sort(key=objective.evaluate)
            events.append({'generation':gen,'migrants':migrated})
        snapshots=[]
        for w,pop in enumerate(pops):
            best=objective.evaluate(pop[0],True)
            snapshots.append(dict(best,world=w+1,diversity=len(set(pop))/population))
        winner=min(snapshots,key=lambda s:s['loss'])
        record={'generation':gen,'worlds':snapshots,'best_world':winner['world'],'best_loss':winner['loss'],'migration':migrated}
        history.append(record)
        if callback: callback(record)
        if gen==generations: break
        next_pops=[]
        for w,pop in enumerate(pops):
            rng=rngs[w]; elite=max(1,int(population*.1)); new=list(pop[:elite])
            def select(): return min(rng.sample(pop,min(3,len(pop))),key=objective.evaluate)
            while len(new)<population:
                child=list(pmx(select(),select(),rng))
                if n>1 and rng.random()<mutation:
                    a,b=sorted(rng.sample(range(n),2))
                    if rng.random()<.5: child[a],child[b]=child[b],child[a]
                    else: child[a:b+1]=reversed(child[a:b+1])
                new.append(repair(child,objective.orders,rng))
            next_pops.append(new)
        pops=next_pops
    best=min(history[-1]['worlds'],key=lambda s:s['loss'])
    return {'best':best,'baseline':objective.evaluate(baseline,True),'history':history,'events':events,'evaluations_cached':len(objective.cache)}
