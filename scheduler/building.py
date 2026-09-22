"""Multi-floor adapter for the existing A*/PMX/Sower engine.

Floor rasters are metric grids, never perspective illustrations. Routing minimizes
travel time on a portal graph of precomputed gray-cost A* segments. It is not a
space-time elevator simulator or a globally fastest cell-level speed-field search.
"""
from __future__ import annotations
import base64
import copy
import math
import random
from heapq import heappop, heappush
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw
from .api import Jobs, image_from_request, number
from .core import Costmap, Order, Objective, DEFAULT_COEFFICIENTS, weights, repair, evolve, sigmoid

MODEL_VERSION = 'multifloor-operational-v1'
FEATURE_KEYS = ('importance', 'wait', 'risk', 'distance', 'slow')
FORMULAS = {
    'score': 'zⱼ = b + aᴵ Iⱼ/10 + aᵂ min(Eⱼ/τⱼ, 3) + aᴿ Rⱼ + aᴰ min(D₀ⱼ/50 m, 3) + aⱽ (1 − min(vⱼ,v₀)/v₀)',
    'weight': 'σ(z) = 1/(1 + exp(−z));  ωⱼ = 1 + 9σ(zⱼ)',
    'matrix': 'wᵢⱼ = ωⱼ for order destinations i ≠ j; wⱼᵢ = ωᵢ; diagonal / START / END columns = 0',
    'arrival': 'Aπ₁ = T₀,π₁;  Aπₖ = Aπₖ₋₁ + Sπₖ₋₁ + Tπₖ₋₁,πₖ',
    'objective': 'L = Tfinish + λ Σⱼ(ωⱼ Aⱼ)/Σⱼωⱼ + μ Σⱼ[Rⱼ max(0,Eⱼ+Aⱼ−τⱼ)/τⱼ] + ν Dtotal',
    'grid': 'g(p) = 1 + γ(255−pixel(p))/255;  cₐᵦ = Δsₐᵦ [g(a)+g(b)]/2',
    'travel': 'Twalk = Σ₍ₐ,ᵦ₎ cₐᵦ/vₐᵦ;  Televator = wait + door + ride (seconds)',
    'selection': 'Pᵢⱼ = argmin over portal-graph paths Σₑ Tₑ; Tᵢⱼ = Σₑ∈Pᵢⱼ Tₑ; Dᵢⱼ = Σwalk∈Pᵢⱼ Dwalk',
}


def png_url(image: Image.Image) -> str:
    stream = BytesIO()
    image.save(stream, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode()


def demo_floor(level: int) -> Image.Image:
    """Synthetic occupancy fixture with explicit doors and no rendering noise."""
    image = Image.new('L', (192, 160), 255)
    d = ImageDraw.Draw(image)
    d.rectangle((0, 0, 191, 159), outline=0, width=4)
    def room(box, door):
        d.rectangle(box, fill=215, outline=0, width=2)
        d.rectangle(door, fill=255)
    for x in (6, 44, 82, 120, 158):
        room((x, 6, x+27, 34), (x+7, 31, x+20, 35))
        room((x, 125, x+27, 153), (x+7, 124, x+20, 128))
    for y in (44, 92):
        room((6, y, 33, y+23), (30, y+5, 34, y+18))
        room((158, y, 185, y+23), (157, y+5, 161, y+18))
    for x in (48, 116):
        for y in (50, 94):
            room((x, y, x+28, y+17), (x+8, y+14, x+21, y+18))
    d.ellipse((88, 72, 104, 88), fill=205)
    # Different, well-defined obstacles on each floor; not artificial scan noise.
    d.rectangle((134 if level == 1 else 50, 76, 140 if level == 1 else 56, 84), fill=0)
    return image


def demo_scene() -> dict:
    placements = [('F1',20,20),('F1',96,20),('F1',172,140),
                  ('F2',20,140),('F2',96,140),('F2',172,20)]
    return {
        'schema_version': 2,
        'floors': [{'id':f'F{k}', 'name':f'{k}F', 'resolution':.15,
                    'map_data':png_url(demo_floor(k))} for k in (1,2)],
        'start': {'floor':'F1','x':96,'y':112}, 'end':None,
        'orders': [dict(id=chr(65+i),floor=f,x=x,y=y,importance=8 if i==4 else 5,
                        waited=180 if i==4 else 0,patience=300,risk=.5,speed=.8,service=10,forbidden=[])
                   for i,(f,x,y) in enumerate(placements)],
        'portals': [dict(id=f'E{k}', a=dict(floor='F1',x=x,y=y),b=dict(floor='F2',x=x,y=y),
                         wait=15,door=6,ride=8,reverse_wait=20,enabled=True)
                    for k,(x,y) in enumerate(((20,80),(96,40),(172,80)),1)],
        'settings':dict(radius=.2,threshold=100,gray_cost=2,cruise=.8,local_radius=1,
                        priority=1,risk_penalty=120,distance_penalty=1,return_to_start=True,
                        population=40,generations=40,worlds=3,sower=True,interval=10,migration=.15,mutation=.2,seed=42),
        'coefficients':dict(DEFAULT_COEFFICIENTS),
    }


def validate_scene(data: dict, require_orders: bool = True, check_clearance: bool = True) -> dict:
    if not isinstance(data, dict):
        raise ValueError('請提供場景 JSON 物件。')
    scene = copy.deepcopy(data)
    if scene.get('schema_version', 2) != 2:
        raise ValueError('不支援的場景版本；請使用 schema_version 2。')
    raw_cfg = scene.get('settings', {})
    if not isinstance(raw_cfg, dict):
        raise ValueError('settings 必須是物件。')
    spec = {'radius':(.2,0,2), 'threshold':(100,0,254), 'gray_cost':(2,0,10),
            'cruise':(.8,.05,3), 'local_radius':(1,0,10), 'priority':(1,0,20),
            'risk_penalty':(120,0,2000), 'distance_penalty':(1,0,20),
            'population':(40,10,200), 'generations':(40,1,300), 'worlds':(3,1,8),
            'interval':(10,1,100), 'migration':(.15,0,.5), 'mutation':(.2,0,1), 'seed':(42,0,2147483647)}
    ints = {'threshold','population','generations','worlds','interval','seed'}
    cfg = {k:number(raw_cfg.get(k,d), k, lo, hi, k in ints) for k,(d,lo,hi) in spec.items()}
    for k,d in [('return_to_start',True), ('sower',True)]:
        if not isinstance(raw_cfg.get(k,d), bool):
            raise ValueError(f'{k} 必須是布林值。')
        cfg[k] = raw_cfg.get(k,d)
    if raw_cfg.get('mode','operational') != 'operational':
        raise ValueError('多樓層介面使用 operational 模式；揭露書比較請用 /legacy。')
    if cfg['population']*(cfg['generations']+1)*(cfg['worlds'] if cfg['sower'] else 1)>300000:
        raise ValueError('候選預算超過 300,000，請降低世代、族群或世界數。')
    c = scene.get('coefficients',{})
    if not isinstance(c,dict):
        raise ValueError('coefficients 必須是物件。')
    coefficients = {k:number(c.get(k,v),k,-10 if k=='bias' else 0,10) for k,v in DEFAULT_COEFFICIENTS.items()}
    def identifier(value, label):
        if not isinstance(value,str) or not value.strip() or len(value)>40:
            raise ValueError(f'{label} 必須為 1–40 字元。')
        return value
    floors = scene.get('floors')
    if not isinstance(floors,list) or not 1<=len(floors)<=4:
        raise ValueError('請設定 1–4 個樓層。')
    grids = {}; views = []; total_pixels = 0
    for f in floors:
        if not isinstance(f,dict): raise ValueError('樓層必須是物件。')
        fid = identifier(f.get('id'),'樓層 ID')
        if fid in grids: raise ValueError('樓層 ID 不可重複。')
        resolution = number(f.get('resolution',.1),'m/px',.01,2)
        if not f.get('map_data'): raise ValueError('每個樓層需要獨立 map_data。')
        image = image_from_request(f)
        total_pixels += image.width*image.height
        if total_pixels > 524288: raise ValueError('場景網格總量超過 524,288 格。')
        pixels = np.array(image)
        unknown = f.get('unknown_value')
        if unknown is not None:
            unknown = number(unknown,'未知區域灰階',0,254,True)
            pixels[pixels==unknown] = 0  # explicit per-floor unknown semantics
        grid = Costmap(pixels,resolution,cfg['threshold'],cfg['radius'],cfg['gray_cost'])
        grids[fid] = grid
        views.append(dict(id=fid,name=identifier(f.get('name',fid),'樓層名稱'),resolution=resolution,
                          width=grid.width,height=grid.height,image=png_url(Image.fromarray(pixels)),
                          blocked_rows=[''.join('1' if v else '0' for v in row) for row in grid.blocked]))
    def point(p):
        if not isinstance(p,dict) or p.get('floor') not in grids:
            raise ValueError('節點需含有效的 floor、x、y。')
        q = dict(floor=p['floor'],x=number(p.get('x'),'x',0,511,True),y=number(p.get('y'),'y',0,511,True))
        if check_clearance and not grids[q['floor']].valid((q['x'],q['y'])):
            raise ValueError(f"{q['floor']} ({q['x']},{q['y']}) 位於牆、未知區域或安全膨脹區。")
        return q
    start = point(scene.get('start')); end = point(scene['end']) if scene.get('end') is not None else None
    raw = scene.get('orders',[])
    if not isinstance(raw,list) or not (1 if require_orders else 0)<=len(raw)<=30:
        raise ValueError('請設定 1–30 筆訂單。')
    orders=[]; points=[start]; ids=set()
    for o in raw:
        if not isinstance(o,dict): raise ValueError('訂單必須是物件。')
        oid=identifier(o.get('id'),'訂單 ID')
        if oid in ids or oid in ('START','END'): raise ValueError('訂單 ID 重複或使用了保留名稱。')
        ids.add(oid); p=point(o)
        forbidden=o.get('forbidden',[])
        if not isinstance(forbidden,list): raise ValueError('禁止順位必須是陣列。')
        forbidden=tuple(number(v,'禁止順位',1,len(raw),True) for v in forbidden)
        values={k:number(o.get(k,d),k,lo,hi) for k,d,lo,hi in [
            ('importance',5,0,10),('waited',0,0,86400),('patience',300,1,86400),
            ('risk',.5,0,1),('speed',.8,.05,3),('service',10,0,3600)]}
        orders.append(Order(oid,p['x'],p['y'],**values,forbidden=forbidden)); points.append(p)
    if end is not None: points.append(end)
    repair(tuple(range(len(orders))),orders,random.Random(cfg['seed']))
    raw_portals=scene.get('portals',[])
    if not isinstance(raw_portals,list) or len(raw_portals)>12: raise ValueError('最多 12 條電梯連線。')
    portals=[]; seen=set()
    for p in raw_portals:
        if not isinstance(p,dict): raise ValueError('電梯連線必須是物件。')
        pid=identifier(p.get('id'),'電梯 ID')
        if pid in seen: raise ValueError('電梯 ID 不可重複。')
        seen.add(pid)
        enabled=p.get('enabled',True)
        if not isinstance(enabled,bool): raise ValueError('電梯 enabled 必須是布林值。')
        a,b=point(p.get('a')),point(p.get('b'))
        if a['floor']==b['floor']: raise ValueError('電梯必須連接不同楼層。')
        values={k:number(p.get(k,d),k,0,3600) for k,d in [('wait',15),('door',6),('ride',8),('reverse_wait',p.get('wait',15))]}
        portals.append(dict(id=pid,a=a,b=b,enabled=enabled,**values))
    return dict(grids=grids,views=views,points=points,orders=orders,portals=portals,
                cfg=cfg,coefficients=coefficients,custom_end=end is not None)


def prepare_building(v: dict, progress=lambda x,y:None, cancelled=lambda:False, terminal_pairs=None) -> dict:
    """Bidirectional connectivity, directed time, explicit floor-tagged segments.

    A disconnected walking pair is omitted, not fatal: another floor can provide
    a valid detour. Every terminal pair must ultimately be reachable.
    """
    points=v['points']; n=len(points); cfg=v['cfg']; grids=v['grids']
    anchors=list(points); elevator_edges=[]
    for portal in v['portals']:
        if not portal['enabled']: continue
        a=len(anchors); anchors.extend([portal['a'],portal['b']])
        for src,dst,wait in [(a,a+1,portal['wait']),(a+1,a,portal['reverse_wait'])]:
            elevator_edges.append((src,dst,dict(kind='elevator',id=portal['id'],
                start=anchors[src],end=anchors[dst],wait=wait,door=portal['door'],ride=portal['ride'],
                time=wait+portal['door']+portal['ride'],distance=0.,effort=0.)))
    walk={}; cache={}; pairs=[(i,j) for i in range(len(anchors)) for j in range(i+1,len(anchors)) if anchors[i]['floor']==anchors[j]['floor']]
    requested = None if terminal_pairs is None else set(terminal_pairs)
    if requested is not None:
        pairs = [(i,j) for i,j in pairs if i>=n or j>=n or (i,j) in requested or (j,i) in requested]
    for done,(i,j) in enumerate(pairs,1):
        if cancelled(): raise InterruptedError('已停止規劃')
        a,b=anchors[i],anchors[j]; fid=a['floor']; g=grids[fid]
        p,q=(a['x'],a['y']),(b['x'],b['y']); key=(fid,p,q)
        if key not in cache:
            try:
                path,d,c=g.astar(p,q,cancelled)
                cache[key]=(path,d,c); cache[(fid,q,p)]=(path[::-1],d,c)
            except ValueError:
                cache[key]=cache[(fid,q,p)]=None
        found=cache[key]
        if found is not None:
            path,d,c=found
            walk[i,j]=dict(kind='walk',floor=fid,path=path,distance=d,effort=c,time=c/cfg['cruise'])
            walk[j,i]=dict(walk[i,j],path=path[::-1])
        progress(done,len(pairs)+n*n)
    adjacency={i:[] for i in range(len(anchors))}
    for (i,j),segment in walk.items(): adjacency[i].append((j,segment))
    for i,j,segment in elevator_edges: adjacency[i].append((j,segment))
    distance=np.zeros((n,n)); travel=distance.copy(); effort=distance.copy(); segments={}
    for i in range(n):
        for j in range(n):
            if requested is not None and (i,j) not in requested: continue
            if cancelled(): raise InterruptedError('已停止規劃')
            if i==j: segments[f'{i}:{j}']=[]; continue
            allowed={i,j,*range(n,len(anchors))}; best={i:0.}; previous={}; heap=[(0.,i)]
            while heap:
                t,u=heappop(heap)
                if t!=best[u]: continue
                if u==j: break
                for dest,original in adjacency[u]:
                    if dest not in allowed: continue
                    edge=original
                    if dest==j and edge['kind']=='walk' and 1<=j<=len(v['orders']):
                        # Same approximation as legacy: local speed on final walk leg.
                        order=v['orders'][j-1]; grid=grids[edge['floor']]; dt=0.
                        for a,b in zip(edge['path'],edge['path'][1:]):
                            ds=math.dist(a,b)*grid.resolution
                            g=(grid.cost[a[1],a[0]]+grid.cost[b[1],b[0]])/2
                            near=math.hypot((a[0]+b[0])/2-order.x,(a[1]+b[1])/2-order.y)*grid.resolution<=cfg['local_radius']
                            dt+=ds*g/(min(cfg['cruise'],order.speed) if near else cfg['cruise'])
                        edge=dict(edge,time=float(dt))
                    nt=t+edge['time']
                    if nt<best.get(dest,math.inf):
                        best[dest]=nt; previous[dest]=(u,edge); heappush(heap,(nt,dest))
            if j not in best:
                labels=v.get('labels') or ['START']+[o.id for o in v['orders']]+(['END'] if v['custom_end'] else [])
                raise ValueError(f'{labels[i]} → {labels[j]} 不可達；請檢查樓層、電梯啟用狀態及門寬。')
            path=[]; cursor=j
            while cursor!=i:
                cursor,edge=previous[cursor]; path.append(edge)
            path.reverse(); segments[f'{i}:{j}']=path
            travel[i,j]=sum(s['time'] for s in path)
            distance[i,j]=sum(s['distance'] for s in path)
            effort[i,j]=sum(s['effort'] for s in path)
            progress(len(pairs)+i*n+j+1,len(pairs)+n*n)
    return dict(points=points,distance=distance,travel=travel,effort=effort,segments=segments)


class ExplainedObjective(Objective):
    def evaluate(self, route, details=False):
        result=super().evaluate(route,details)
        if details and math.isfinite(result['loss']):
            result['components']=dict(finish=result['duration'],priority=self.priority*result['weighted_arrival'],
                risk=self.risk_penalty*result['risk_cost'],distance=self.distance_penalty*result['distance'])
            for row in result['schedule']:
                row['floor']=self.m['points'][row['node']]['floor']
        return result


class BuildingJobs(Jobs):
    validate = staticmethod(validate_scene)

    def _run(self, id, v):
        item=self.items[id]; cancelled=item['cancel'].is_set
        def update(**kw):
            with self.lock: item.update(kw)
        try:
            update(status='running',phase='樓層 A* 與電梯圖')
            m=prepare_building(v,lambda done,total:update(progress=round(35*done/max(1,total),1)),cancelled)
            cfg=v['cfg']; orders=v['orders']; c=v['coefficients']
            rows=weights(orders,m,cfg['cruise'],c)
            for row in rows:
                row['contributions']={k:c[k]*x for k,x in zip(FEATURE_KEYS,row['features'])}
                row['bias']=c['bias']; row['sigmoid']=sigmoid(row['z'])
            n=len(m['points'])
            w=[[rows[j-1]['weight'] if i!=j and 1<=j<=len(orders) else 0. for j in range(n)] for i in range(n)]
            meta=dict(model_version=MODEL_VERSION,formulas=FORMULAS,weights=rows,weight_matrix=w,
                      distance_matrix=m['distance'].tolist(),time_matrix=m['travel'].tolist(),
                      points=m['points'],segments=m['segments'],labels=['START']+[o.id for o in orders]+(['END'] if v['custom_end'] else []),
                      coefficients=c,settings=cfg,floors=v['views'],portals=v['portals'])
            update(meta=meta,phase='PMX / Sower 排程')
            obj=ExplainedObjective(orders,m,rows,cfg['return_to_start'],v['custom_end'],cfg['priority'],cfg['risk_penalty'],cfg['distance_penalty'])
            def callback(record):
                with self.lock:
                    item['history'].append(record); item['progress']=35+65*record['generation']/cfg['generations']
            result=evolve(obj,**{k:cfg[k] for k in ('population','generations','worlds','sower','interval','migration','mutation','seed')},callback=callback,cancelled=cancelled)
            result.pop('history')
            if cancelled(): raise InterruptedError('已停止規劃')
            update(status='done',phase='完成',progress=100,result=result)
        except InterruptedError as exc: update(status='cancelled',phase='已停止',error=str(exc))
        except ValueError as exc: update(status='error',phase='無法規劃',error=str(exc))
        except Exception:
            import traceback
            traceback.print_exc(); update(status='error',phase='計算失敗',error='內部錯誤，請查看終端機。')
