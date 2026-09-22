"""Executable tests of real routes, units, objective identities and API snapshots."""
import copy
import itertools
import json
import math
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import numpy as np
from PIL import Image
from scheduler.building import (demo_scene, validate_scene, prepare_building, png_url,
                               ExplainedObjective, BuildingJobs)
from scheduler.core import prepare, weights, sigmoid, evolve


class BuildingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scene=demo_scene(); cls.v=validate_scene(cls.scene); cls.m=prepare_building(cls.v)

    def test_every_walk_stays_inside_its_floor_and_never_cuts_a_corner(self):
        for segments in self.m['segments'].values():
            for s in segments:
                if s['kind']!='walk': continue
                g=self.v['grids'][s['floor']]
                for a,b in zip(s['path'],s['path'][1:]):
                    self.assertTrue(g.valid(a) and g.valid(b))
                    self.assertEqual(max(abs(a[0]-b[0]),abs(a[1]-b[1])),1)
                    if a[0]!=b[0] and a[1]!=b[1]:
                        self.assertTrue(g.valid((a[0],b[1])) and g.valid((b[0],a[1])))
                self.assertAlmostEqual(s['distance'],sum(math.dist(a,b)*g.resolution for a,b in zip(s['path'],s['path'][1:])))

    def test_segments_are_continuous_and_matrix_entries_equal_real_segment_sums(self):
        for key,segments in self.m['segments'].items():
            i,j=map(int,key.split(':')); cursor=self.m['points'][i]
            for s in segments:
                if s['kind']=='walk':
                    self.assertEqual((cursor['floor'],cursor['x'],cursor['y']), (s['floor'],*s['path'][0]))
                    cursor=dict(floor=s['floor'],x=s['path'][-1][0],y=s['path'][-1][1])
                else:
                    self.assertEqual(cursor,s['start']); cursor=s['end']
                    self.assertNotEqual(s['start']['floor'],s['end']['floor'])
                    self.assertAlmostEqual(s['time'],s['wait']+s['door']+s['ride'])
            self.assertEqual(cursor,self.m['points'][j])
            self.assertAlmostEqual(self.m['travel'][i,j],sum(s['time'] for s in segments))
            self.assertAlmostEqual(self.m['distance'][i,j],sum(s['distance'] for s in segments))

    def test_same_xy_on_different_floors_requires_elevator_and_directional_wait(self):
        scene=demo_scene(); scene['start']=copy.deepcopy(scene['portals'][0]['a'])
        scene['orders']=[dict(id='up',**scene['portals'][0]['b'])]
        m=prepare_building(validate_scene(scene))
        self.assertAlmostEqual(m['travel'][0,1],29)
        self.assertAlmostEqual(m['travel'][1,0],34)
        self.assertEqual(m['distance'][0,1],0)  # horizontal distance, not elevator height
        self.assertEqual([s['id'] for s in m['segments']['0:1'] if s['kind']=='elevator'],['E1'])

    def test_disabling_all_elevators_never_creates_a_fake_interfloor_line(self):
        scene=demo_scene()
        for p in scene['portals']: p['enabled']=False
        with self.assertRaisesRegex(ValueError,'不可達'): prepare_building(validate_scene(scene))

    def test_elevator_wait_changes_selected_portal(self):
        scene=demo_scene(); scene['start']=copy.deepcopy(scene['portals'][0]['a'])
        scene['orders']=[dict(id='up',**scene['portals'][0]['b'])]
        scene['portals'][0]['wait']=1000
        m=prepare_building(validate_scene(scene))
        used=[s['id'] for s in m['segments']['0:1'] if s['kind']=='elevator']
        self.assertNotIn('E1',used); self.assertEqual(len(used),1)
        # Reverse wait is different, so the reverse route may have different geometry.
        self.assertNotEqual(m['distance'][0,1],m['distance'][1,0])

    def test_single_floor_is_compatible_with_legacy_preparation(self):
        scene=demo_scene();scene['floors']=scene['floors'][:1];scene['orders']=scene['orders'][:3];scene['portals']=[]
        v=validate_scene(scene);actual=prepare_building(v)
        expected=prepare(v['grids']['F1'],v['orders'],(scene['start']['x'],scene['start']['y']))
        np.testing.assert_allclose(actual['distance'],expected['distance'])
        np.testing.assert_allclose(actual['travel'],expected['travel'])

    def test_weighted_loss_identity_and_service_arrival_recursion(self):
        rows=weights(self.v['orders'],self.m,.8)
        obj=ExplainedObjective(self.v['orders'],self.m,rows)
        out=obj.evaluate(tuple(range(6)),True)
        self.assertAlmostEqual(out['loss'],sum(out['components'].values()))
        t=0.;prev=0
        for i,s in enumerate(out['schedule']):
            t+=self.m['travel'][prev,i+1]
            self.assertAlmostEqual(t,s['arrival']);t+=self.v['orders'][i].service;prev=i+1
        self.assertAlmostEqual(out['duration'],t+self.m['travel'][prev,0])
        expected=sum((1+9*sigmoid(r['z']))*s['arrival'] for r,s in zip(rows,out['schedule']))/sum(r['weight'] for r in rows)
        self.assertAlmostEqual(out['weighted_arrival'],expected)

    def test_fixed_route_sigmoid_derivative_matches_finite_difference(self):
        rows=weights(self.v['orders'],self.m,.8);route=tuple(range(6)); j=2;eps=1e-5
        original=ExplainedObjective(self.v['orders'],self.m,rows).evaluate(route,True)
        arrivals=[s['arrival'] for s in original['schedule']];z=rows[j]['z'];total=sum(r['weight'] for r in rows)
        analytic=9*sigmoid(z)*(1-sigmoid(z))*(arrivals[j]-original['weighted_arrival'])/total
        def at(value):
            w=[r['weight'] for r in rows];w[j]=1+9*sigmoid(value)
            return sum(a*b for a,b in zip(w,arrivals))/sum(w)
        self.assertAlmostEqual(analytic,(at(z+eps)-at(z-eps))/(2*eps),places=7)

    def test_zero_coefficients_remove_feature_contributions(self):
        c=dict(importance=0,wait=0,risk=0,distance=0,slow=0,bias=0)
        rows=weights(self.v['orders'],self.m,.8,c)
        self.assertTrue(all(r['z']==0 and r['weight']==5.5 for r in rows))

    def test_seeded_ga_and_four_order_exact_reference(self):
        scene=demo_scene();scene['orders']=scene['orders'][:4]
        v=validate_scene(scene);m=prepare_building(v);rows=weights(v['orders'],m,.8)
        def run():return evolve(ExplainedObjective(v['orders'],m,rows),population=40,generations=20,worlds=3,seed=42)
        a,b=run(),run();self.assertEqual(a,b)
        obj=ExplainedObjective(v['orders'],m,rows)
        exact=min(obj.evaluate(r) for r in itertools.permutations(range(4)))
        self.assertAlmostEqual(a['best']['loss'],exact)

    def test_cancel_preprocessing(self):
        with self.assertRaises(InterruptedError): prepare_building(self.v,cancelled=lambda:True)

    def test_unknown_and_transparency_are_explicitly_blocked(self):
        for mode in ('unknown','alpha'):
            s=demo_scene();im=Image.new('RGBA',(192,160),(255,255,255,255))
            im.putpixel((96,112),(127,127,127,255) if mode=='unknown' else (255,255,255,0))
            s['floors'][0]['map_data']=png_url(im)
            if mode=='unknown': s['floors'][0]['unknown_value']=127
            with self.subTest(mode=mode),self.assertRaises(ValueError):validate_scene(s)

    def test_preview_allows_repositioning_but_planning_rejects_blocked_node(self):
        s=demo_scene();s['orders'][0]['x']=0
        self.assertTrue(validate_scene(s,check_clearance=False)['views'])
        with self.assertRaisesRegex(ValueError,'膨脹'):validate_scene(s)

    def test_bad_inputs_and_budgets(self):
        mutations=[lambda s:s['portals'][0].update(wait=-1),lambda s:s['orders'][0].update(importance=float('nan')),
                   lambda s:s['floors'][0].update(resolution=0),lambda s:s['orders'][0].update(floor='absent'),
                   lambda s:s['portals'][0].update(b=s['portals'][0]['a']),lambda s:s['portals'][0].update(enabled='false'),
                   lambda s:s['orders'][0].update(id='START'),lambda s:s['settings'].update(generations=300,population=200,worlds=8),
                   lambda s:s['floors'][0].update(map_data=png_url(Image.new('L',(513,4),255)))]
        for mutate in mutations:
            s=demo_scene();mutate(s)
            with self.subTest(mutation=mutate),self.assertRaises(ValueError):validate_scene(s)

    def test_custom_end_is_not_an_order_and_return_flag_is_respected(self):
        s=demo_scene();s['orders']=s['orders'][:1];s['end']=dict(floor='F2',x=96,y=112)
        v=validate_scene(s);m=prepare_building(v);rows=weights(v['orders'],m,.8)
        obj=ExplainedObjective(v['orders'],m,rows,custom_end=True)
        out=obj.evaluate((0,),True);self.assertEqual(out['route'],[0,1,2]);self.assertEqual(len(out['schedule']),1)
        open_obj=ExplainedObjective(v['orders'],m,rows,return_to_start=False)
        self.assertEqual(open_obj.evaluate((0,),True)['route'],[0,1])


class BuildingHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import Handler
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.url=f'http://127.0.0.1:{cls.server.server_address[1]}'
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def request(self,path,data=None,**headers):
        req=Request(self.url+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json',**headers})
        try:
            with urlopen(req,timeout=30) as r:return r.status,r.read(),r.headers
        except HTTPError as e:return e.code,e.read(),e.headers
    def test_full_http_job_snapshot_matrix_formula_and_export_roundtrip(self):
        status,body,headers=self.request('/studio');self.assertEqual(status,200)
        self.assertIn("script-src 'self'",headers['Content-Security-Policy'])
        self.assertIn(b'studio.js',body)
        s=json.loads(self.request('/api/studio/demo')[1]);s['settings'].update(generations=6,population=20,worlds=2,interval=2)
        status,body,_=self.request('/api/studio/jobs',s);self.assertEqual(status,202,body);jid=json.loads(body)['id']
        for _ in range(200):
            _,body,_=self.request('/api/studio/jobs/'+jid);job=json.loads(body)
            if job['status'] in ('done','error','cancelled'):break
            time.sleep(.03)
        self.assertEqual(job['status'],'done',job);meta=job['meta']
        self.assertEqual(len(job['history']),7);self.assertTrue(meta['segments']['0:4'])
        self.assertEqual(len(meta['weight_matrix']),7);self.assertEqual(len(meta['formulas']),8)
        for j,w in enumerate(meta['weights'],1):
            self.assertAlmostEqual(w['z'],w['bias']+sum(w['contributions'].values()))
            self.assertAlmostEqual(w['weight'],1+9*w['sigmoid'])
            self.assertEqual(meta['weight_matrix'][0][j],w['weight'])
            self.assertEqual(meta['weight_matrix'][j][0],0);self.assertEqual(meta['weight_matrix'][j][j],0)
        self.assertAlmostEqual(job['result']['best']['loss'],sum(job['result']['best']['components'].values()))
        restored=validate_scene(json.loads(json.dumps(s)));m=prepare_building(restored)
        np.testing.assert_allclose(m['travel'],meta['time_matrix'])
    def test_invalid_and_cross_origin_writes_do_not_start_jobs(self):
        self.assertEqual(self.request('/api/studio/jobs',[],Origin='https://outside.example')[0],403)
        self.assertEqual(self.request('/api/studio/jobs',[])[0],400)
        self.assertEqual(self.request('/api/studio/jobs/missing')[0],404)
        self.assertEqual(self.request('/api/studio/jobs/missing?after=-1')[0],400)
        s=demo_scene();s['orders'][0]['x']=0
        self.assertEqual(self.request('/api/studio/preview',s)[0],200)
        self.assertEqual(self.request('/api/studio/jobs',s)[0],400)

if __name__=='__main__':unittest.main()
