import copy
import itertools
import json
import math
import time
import unittest
from unittest.mock import patch
import numpy as np
from scheduler.editor import (editor_demo, preview_editor, validate_editor, EditorJobs,
                              EditorObjective)
from scheduler.building import prepare_building
from scheduler.core import weights, evolve
from test_http import HTTPTests


class EditorTests(unittest.TestCase):
    def setUp(self): self.scene=editor_demo()
    def test_preview_never_calls_ga_and_uses_consecutive_edges(self):
        with patch('scheduler.editor.evolve',side_effect=AssertionError('GA was called')):
            v=preview_editor(self.scene)
        self.assertIsNone(v['error']);self.assertEqual(len(v['legs']),7)
        self.assertEqual([(l['source'],l['target']) for l in v['legs']],[(i,i+1) for i in range(7)])
        self.assertAlmostEqual(v['distance'],sum(s['distance'] for l in v['legs'] for s in l['segments']))
        self.assertAlmostEqual(v['time'],sum(s['time'] for l in v['legs'] for s in l['segments']))
        self.assertTrue(any(s['kind']=='elevator' for l in v['legs'] for s in l['segments']))

    def test_zero_one_two_nodes_editable_but_not_ga(self):
        for n in (0,1,2):
            self.scene['nodes']=editor_demo()['nodes'][:n]
            p=preview_editor(self.scene)
            self.assertIsNone(p['error']);self.assertEqual(len(p['legs']),max(0,n-1))
            with self.assertRaises(ValueError):validate_editor(self.scene)

    def test_roles_are_order_based_with_endpoint_weights_excluded(self):
        self.scene['nodes'].reverse()
        self.scene['nodes'][0]['importance']=10
        v=validate_editor(self.scene)
        self.assertEqual(v['points'][0]['floor'],self.scene['nodes'][0]['floor'])
        self.assertEqual(v['points'][-1]['x'],self.scene['nodes'][-1]['x'])
        self.assertEqual(len(v['orders']),len(self.scene['nodes'])-2)
        self.assertFalse(v['cfg']['return_to_start']);self.assertTrue(v['custom_end'])
        self.scene['nodes'][1]['id']='START'
        self.assertEqual(validate_editor(self.scene)['labels'][1],'START')

    def test_reject_bad_inputs_and_no_partial_routes(self):
        for mutate in [lambda s:s['nodes'].append(copy.deepcopy(s['nodes'][0])),
                       lambda s:s['nodes'][1].update(id=''),lambda s:s['nodes'][1].update(x=1.1),
                       lambda s:s['nodes'][1].update(floor='absent'),lambda s:s.update(schema_version=99)]:
            s=copy.deepcopy(self.scene);mutate(s)
            with self.assertRaises(ValueError):validate_editor(s)
        for n in ('importance','waited','speed'):
            s=copy.deepcopy(self.scene);s['nodes'][1][n]=math.nan
            with self.assertRaises(ValueError):validate_editor(s)
        self.scene['nodes'][2]['x']=0
        p=preview_editor(self.scene);self.assertTrue(p['error']);self.assertEqual(p['legs'],[])

    def test_disabled_elevators_fail_without_cross_floor_shortcuts(self):
        for p in self.scene['portals']:p['enabled']=False
        out=preview_editor(self.scene)
        self.assertTrue(out['error']);self.assertEqual(out['legs'],[])
        with self.assertRaises(ValueError):prepare_building(validate_editor(self.scene))

    def test_preview_does_not_apply_positional_constraints(self):
        self.scene['nodes'][1]['forbidden']=[1,2,3,4,5,6]
        self.assertIsNone(preview_editor(self.scene)['error'])
        with self.assertRaises(ValueError):validate_editor(self.scene)

    def test_preview_matches_same_selected_paths_as_full_matrix(self):
        self.scene['nodes']=self.scene['nodes'][:4]
        v=validate_editor(self.scene);full=prepare_building(v);out=preview_editor(self.scene)
        for leg in out['legs']:
            i,j=leg['source'],leg['target']
            self.assertEqual(leg['segments'],full['segments'][f'{i}:{j}'])
            self.assertAlmostEqual(leg['time'],full['travel'][i,j])

    def test_tracking_is_optional_deterministic_and_does_not_change_search(self):
        self.scene['nodes']=self.scene['nodes'][:5]
        v=validate_editor(self.scene);m=prepare_building(v);weight_rows=weights(v['orders'],m,.8)
        def obj():return EditorObjective(v['orders'],m,weight_rows,False,True,labels=v['labels'])
        a=evolve(obj(),generations=8,worlds=3,interval=2,population=20,elite_tracking=True)
        b=evolve(obj(),generations=8,worlds=3,interval=2,population=20)
        exact=min(obj().evaluate(r) for r in itertools.permutations(range(3)))
        self.assertAlmostEqual(a['best']['loss'],exact)
        self.assertEqual(a['best']['loss'],b['best']['loss']);self.assertEqual(a['best']['route'],b['best']['route'])
        for h in a['history']:
            for w in h['worlds']:
                self.assertEqual(w['route'][0],0);self.assertEqual(w['route'][-1],4)
                self.assertEqual(w['elites'][0]['loss'],w['loss'])
                self.assertEqual(w['elites'][0]['order'],w['route'][1:-1])
                self.assertEqual(w['elite_count'],2)
            for t in h['transfers']:
                self.assertNotEqual(t['source'],t['target'])
                self.assertAlmostEqual(t['loss'],obj().evaluate(tuple(g-1 for g in t['order'])))
        single=evolve(obj(),generations=5,sower=False,elite_tracking=True)
        self.assertTrue(all(len(h['worlds'])==1 and not h['transfers'] for h in single['history']))

    def test_preview_limiter_returns_retry_without_starting_more_work(self):
        from scheduler.editor import _preview_lock
        with _preview_lock:
            out=preview_editor(self.scene)
        self.assertTrue(out['retry']);self.assertEqual(out['legs'],[])


class EditorHTTPTests(HTTPTests):
    def test_editor_end_to_end_and_origin_validation(self):
        status,body=self.request('/');self.assertEqual(status,200);self.assertIn(b'editor.js',body)
        self.assertEqual(self.request('/editor.js')[0],200)
        self.assertEqual(self.request('/studio')[0],200)
        status,body=self.request('/api/editor/demo');self.assertEqual(status,200);scene=json.loads(body)
        scene['nodes']=scene['nodes'][:5]
        scene['settings'].update(generations=6,population=20,worlds=2,interval=2)
        status,body=self.request('/api/editor/preview',scene);self.assertEqual(status,200);self.assertEqual(len(json.loads(body)['legs']),4)
        self.assertEqual(self.request('/api/editor/jobs',scene,Origin='https://other.example')[0],403)
        status,body=self.request('/api/editor/jobs',scene);self.assertEqual(status,202,body);id=json.loads(body)['id']
        for _ in range(150):
            _,body=self.request('/api/editor/jobs/'+id);v=json.loads(body)
            if v['status'] not in ('queued','running'):break
            time.sleep(.02)
        self.assertEqual(v['status'],'done',v)
        self.assertEqual(len(v['history']),7)
        self.assertEqual(v['meta']['labels'],[n['id'] for n in scene['nodes']])
        self.assertEqual(len(v['meta']['weights']),3)
        w=np.array(v['meta']['weight_matrix']);self.assertTrue((w[:,0]==0).all());self.assertTrue((w[:,-1]==0).all())
        best=v['result']['best'];self.assertAlmostEqual(sum(best['components'].values()),best['loss'])
        self.assertEqual(best['route'][0],0);self.assertEqual(best['route'][-1],4)
        self.assertEqual(self.request('/api/editor/jobs/missing')[0],404)
        self.assertEqual(self.request('/api/editor/jobs/'+id+'?after=-1')[0],400)
        self.assertEqual(self.request('/api/editor/preview',dict(scene,nodes=[{'id':'bad'}]))[0],400)
