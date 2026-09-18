import unittest
import itertools
import math
import random
import numpy as np
from scheduler.core import Costmap,Order,prepare,weights,Objective,evolve,pmx,repair
from scheduler.api import validate, ROOT
from PIL import Image

class GridTests(unittest.TestCase):
    def test_astar_detour_and_corner_safety(self):
        a=np.full((30,30),255,dtype=np.uint8);a[1:24,15]=0
        g=Costmap(a,resolution=1,radius=0)
        path,d,_=g.astar((5,5),(25,5))
        self.assertGreater(d,20)
        for p,q in zip(path,path[1:]):
            self.assertTrue(g.valid(p));self.assertTrue(g.valid(q))
            self.assertLessEqual(max(abs(q[0]-p[0]),abs(q[1]-p[1])),1)
            if p[0]!=q[0] and p[1]!=q[1]:
                self.assertTrue(g.valid((p[0],q[1])));self.assertTrue(g.valid((q[0],p[1])))
    def test_no_diagonal_corner_escape(self):
        a=np.zeros((8,8),dtype=np.uint8);a[2,2]=a[3,3]=255
        with self.assertRaises(ValueError):Costmap(a,1,radius=0).astar((2,2),(3,3))
    def test_inflation_and_disconnection(self):
        a=np.full((20,20),255,dtype=np.uint8);a[:,10]=0
        g=Costmap(a,1,radius=1)
        self.assertFalse(g.valid((9,7)))
        with self.assertRaises(ValueError):g.astar((4,7),(15,7))
    def test_gray_cost_changes_route(self):
        a=np.full((20,40),255,dtype=np.uint8);a[9:12,10:30]=150
        g=Costmap(a,1,radius=0,gray_cost=10)
        path,_,_=g.astar((4,10),(35,10))
        self.assertTrue(all(a[y,x]==255 for x,y in path))
    def test_astar_equals_dijkstra(self):
        # Independent reference on a weighted 8-connected grid.
        from heapq import heappop,heappush
        a=np.full((15,16),255,dtype=np.uint8);a[3:10,7]=0;a[10:13,4:9]=180
        g=Costmap(a,1,radius=0);start=(2,2);end=(12,12)
        queue=[(0,start)];seen={start:0}
        while queue:
            cost,p=heappop(queue)
            if cost!=seen[p]:continue
            if p==end:break
            for dx,dy in itertools.product((-1,0,1),repeat=2):
                if dx==dy==0:continue
                q=(p[0]+dx,p[1]+dy)
                if not g.valid(q) or (dx and dy and (not g.valid((p[0]+dx,p[1])) or not g.valid((p[0],p[1]+dy)))):continue
                v=cost+math.hypot(dx,dy)*(g.cost[p[1],p[0]]+g.cost[q[1],q[0]])/2
                if v<seen.get(q,math.inf):seen[q]=v;heappush(queue,(v,q))
        self.assertAlmostEqual(g.astar(start,end)[2],seen[end])

class GATests(unittest.TestCase):
    def objective(self,orders=None,**kw):
        orders=orders or [Order('a',8,8),Order('b',25,8),Order('c',25,25),Order('d',8,25)]
        grid=Costmap(np.full((35,35),255,dtype=np.uint8),1,radius=0)
        m=prepare(grid,orders,(4,4));return Objective(orders,m,weights(orders,m,.8),**kw)
    def test_pmx_is_permutation(self):
        r=random.Random(12)
        for n in range(1,31):
            for _ in range(40):
                a=tuple(r.sample(range(n),n));b=tuple(r.sample(range(n),n))
                self.assertEqual(sorted(pmx(a,b,r)),list(range(n)))
    def test_feasible_constraints_and_infeasible(self):
        orders=[Order('a',8,8,forbidden=(1,2)),Order('b',25,8,forbidden=(2,3)),Order('c',25,25,forbidden=(1,3))]
        r=repair((0,1,2),orders,random.Random(1))
        self.assertEqual(r,(1,2,0))
        with self.assertRaises(ValueError):repair((0,1),[Order('a',1,1,forbidden=(1,)),Order('b',2,2,forbidden=(1,))],random.Random(0))
        out=evolve(self.objective(orders),population=20,generations=5)
        for h in out['history']:
            for w in h['worlds']:self.assertEqual(w['route'][1:-1],[2,3,1])
    def test_exact_small_problem_and_monotonicity(self):
        obj=self.objective();out=evolve(obj,population=40,generations=30,worlds=3,interval=5,seed=7)
        exact=min(obj.evaluate(p) for p in itertools.permutations(range(4)))
        self.assertAlmostEqual(out['best']['loss'],exact)
        self.assertLessEqual(out['best']['loss'],out['baseline']['loss'])
        for w in range(3):
            vals=[h['worlds'][w]['loss'] for h in out['history']]
            self.assertTrue(all(b<=a+1e-10 for a,b in zip(vals,vals[1:])))
        self.assertEqual(len(out['events']),6)
    def test_reproducibility_single_small_and_no_sower(self):
        a=evolve(self.objective(),generations=5,seed=2);b=evolve(self.objective(),generations=5,seed=2)
        self.assertEqual(a,b)
        for n in (1,2):
            out=evolve(self.objective([Order(str(i),6+i,8) for i in range(n)]),generations=3,sower=False)
            self.assertEqual(len(out['history'][0]['worlds']),1);self.assertFalse(out['events'])
            self.assertEqual(sorted(out['best']['route'][1:-1]),list(range(1,n+1)))
    def test_urgent_order_and_service_time(self):
        orders=[Order('ordinary',10,15,importance=0,risk=0,service=100),Order('urgent',20,15,importance=10,waited=90,patience=100,risk=1)]
        obj=self.objective(orders,return_to_start=False)
        self.assertLess(obj.evaluate((1,0)),obj.evaluate((0,1)))
        details=obj.evaluate((0,1),True)
        self.assertGreater(details['schedule'][1]['arrival'],100)
    def test_slow_destination_asymmetric_and_end(self):
        orders=[Order('slow',10,15,speed=.1),Order('fast',20,15)]
        grid=Costmap(np.full((35,35),255,dtype=np.uint8),1,radius=0)
        m=prepare(grid,orders,(4,4),end=(30,30),local_radius=3)
        self.assertGreater(m['travel'][2,1],m['travel'][1,2])
        obj=Objective(orders,m,weights(orders,m,.8),custom_end=True)
        self.assertEqual(obj.evaluate((0,1),True)['route'],[0,1,2,3])
    def test_disclosure_formula(self):
        obj=self.objective([Order('a',8,8)],return_to_start=False,mode='disclosure')
        from scheduler.core import sigmoid
        expected=sigmoid(obj.m['distance'][0,1]/(10*(1+obj.rows[0]['weight'])))
        self.assertAlmostEqual(obj.evaluate((0,)),expected)
    def test_cancel(self):
        with self.assertRaises(InterruptedError):evolve(self.objective(),cancelled=lambda:True)

class ValidationTests(unittest.TestCase):
    def base(self):return {'map':'hotel','start':[15,80],'orders':[{'id':'A','x':28,'y':28}]}
    def test_maps_connected_and_footprint_clear(self):
        import json
        for name in ('hotel','restaurant','warehouse'):
            meta=json.loads((ROOT/'data/map'/f'{name}.json').read_text());grid=Costmap(Image.open(ROOT/'data/map'/f'{name}.png'))
            for point in meta['points']:
                path,_,_=grid.astar(tuple(meta['start']),tuple(point))
                self.assertTrue(all(grid.valid(p) for p in path))
    def test_bad_inputs(self):
        for field,value in [('speed',0),('patience',0),('importance',float('nan')),('x',3.2)]:
            d=self.base();d['orders'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validate(d)
        d=self.base();d['orders']*=2
        with self.assertRaises(ValueError):validate(d)
        d=self.base();d['orders'][0]['x']=0
        with self.assertRaises(ValueError):validate(d)
        d=self.base();d['settings']={'population':200,'generations':300,'worlds':8}
        with self.assertRaises(ValueError):validate(d)
    def test_transparent_is_occupied(self):
        import base64
        from io import BytesIO
        from scheduler.api import image_from_request
        im=Image.new('RGBA',(20,20),(255,255,255,0));buf=BytesIO();im.save(buf,format='PNG')
        out=image_from_request({'map_data':base64.b64encode(buf.getvalue()).decode()})
        self.assertEqual(out.getpixel((5,5)),0)

if __name__=='__main__':unittest.main()
