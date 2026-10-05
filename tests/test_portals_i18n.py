"""Draft elevator preflight and bilingual protocol regression tests."""
import copy
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw

from scheduler.editor import editor_demo, starter_scene, preview_editor, preflight_editor, validate_editor, EditorJobs
from scheduler.building import png_url
from scheduler.portals import SceneIssues
from scheduler.messages import localize_payload, exception_payload
from test_http import HTTPTests

ROOT = Path(__file__).resolve().parents[1]

class PortalTests(unittest.TestCase):
    def setUp(self):self.scene=editor_demo()
    def assert_blocked_before_search(self, scene):
        with patch('scheduler.editor.prepare_building',side_effect=AssertionError('A* started')), \
             patch('scheduler.editor.evolve',side_effect=AssertionError('GA started')):
            p=preview_editor(scene)
            self.assertFalse(p['preflight']['ok']);self.assertEqual(p['legs'],[])
            with self.assertRaises(SceneIssues):EditorJobs().start(scene)
        return p['preflight']
    def test_pair_ids_keep_two_elevators_distinct(self):
        for p,name in zip(self.scene['portals'],('Ea','Eb','Ec')):p['id']=name
        check=preflight_editor(self.scene)
        self.assertTrue(check['ok'])
        self.assertEqual(check['portals'][0]['labels'],{'a':'Ea_F1','b':'Ea_F2'})
        self.assertEqual(check['portals'][1]['labels'],{'a':'Eb_F1','b':'Eb_F2'})
    def test_missing_endpoint_none_object_or_partial(self):
        for missing in (None,{}, {'floor':'F2','x':None,'y':80}, {'floor':'F2','x':20}):
            with self.subTest(missing=missing):
                s=copy.deepcopy(self.scene);s['portals'][0]['b']=missing
                check=self.assert_blocked_before_search(s)
                self.assertEqual(check['portals'][0]['state'],'incomplete')
                self.assertEqual(check['issues'][0]['code'],'portal.missing')
    def test_missing_floor_is_reported_before_search(self):
        self.scene['portals'][0]['b']['floor']='3F'
        check=self.assert_blocked_before_search(self.scene)
        self.assertEqual(check['issues'][0]['code'],'portal.floor_missing')
    def test_wall_outside_clearance_blocked(self):
        for x,y in ((0,0),(191,80),(500,500),(-1,10)):
            s=copy.deepcopy(self.scene);s['portals'][0]['b'].update(x=x,y=y)
            check=self.assert_blocked_before_search(s)
            self.assertEqual(check['issues'][0]['code'],'portal.blocked')
    def test_same_floor_not_a_vertical_portal(self):
        self.scene['portals'][0]['b']['floor']='F1'
        check=self.assert_blocked_before_search(self.scene)
        self.assertTrue(any(i['code']=='portal.same_floor' for i in check['issues']))
    def test_disabled_incomplete_is_warning_and_never_routes(self):
        p=self.scene['portals'][0];p['b']=None;p['enabled']=False
        v=validate_editor(self.scene)
        self.assertNotIn(p['id'],[q['id'] for q in v['portals']])
        self.assertTrue(v['preflight']['ok'])
        self.assertTrue(all(i['severity']=='warning' for i in v['preflight']['issues']))
        out=preview_editor(self.scene)
        self.assertIsNone(out['error'])
        self.assertFalse(any(s.get('id')==p['id'] for l in out['legs'] for s in l['segments']))
    def test_enabled_incomplete_blocks_even_if_another_elevator_is_available(self):
        self.scene['portals'][0]['a']['x']=None
        self.assert_blocked_before_search(self.scene)
    def test_complete_repaired_pair_restores_preview(self):
        self.scene['portals'][0]['b']['x']=None
        self.assertFalse(preflight_editor(self.scene)['ok'])
        self.scene['portals'][0]['b']['x']=20
        p=preview_editor(self.scene)
        self.assertTrue(p['preflight']['ok']);self.assertEqual(len(p['legs']),7)
    def test_draft_does_not_autofill_or_mutate_input(self):
        self.scene['portals'][0]['a']={'floor':'F1','x':None,'y':None}
        before=copy.deepcopy(self.scene);out=preview_editor(self.scene)
        self.assertEqual(self.scene,before)
        self.assertIsNone(out['portals'][0]['a']['x'])
        self.assertIsNone(out['portals'][0]['a']['y'])
    def test_disconnected_components_fail_before_astar(self):
        for p in self.scene['portals']:p['enabled']=False
        check=self.assert_blocked_before_search(self.scene)
        self.assertTrue(any(i['code']=='route.disconnected' for i in check['issues']))
    def test_disconnected_node_gets_non_mutating_move_proposal(self):
        scene=starter_scene();image=Image.new('L',(40,24),255)
        draw=ImageDraw.Draw(image);draw.rectangle((0,0,39,23),outline=0,width=1);draw.line((20,0,20,23),fill=0,width=1)
        scene['floors'][0]['map_data']=png_url(image)
        scene['settings']['radius']=0
        scene['nodes']=[{'id':'N1','floor':'sheet-1','x':8,'y':12},
                        {'id':'N7','floor':'sheet-1','x':31,'y':12}]
        before=copy.deepcopy(scene);check=preflight_editor(scene)
        proposal=next(s for s in check['suggestions'] if s['kind']=='node.move' and s['node']=='N7')
        self.assertEqual(scene,before)
        self.assertEqual(proposal['before'],scene['nodes'][1])
        self.assertEqual(proposal['after']['floor'],'sheet-1')
        self.assertLess(proposal['after']['x'],20)
    def test_incomplete_enabled_portal_gets_disable_proposal(self):
        self.scene['portals'][0]['b']=None
        check=preflight_editor(self.scene)
        proposal=next(s for s in check['suggestions'] if s['kind']=='portal.disable')
        self.assertEqual(proposal['portal'],self.scene['portals'][0]['id'])
        self.assertEqual(proposal['after'],{'enabled':False})
    def test_blocked_node_gets_nearest_valid_move_proposal(self):
        scene=starter_scene();scene['settings']['radius']=0
        scene['nodes']=[{'id':'N1','floor':'sheet-1','x':20,'y':20},
                        {'id':'N2','floor':'sheet-1','x':0,'y':0}]
        check=preflight_editor(scene)
        proposal=next(s for s in check['suggestions'] if s['kind']=='node.move' and s['node']=='N2')
        self.assertEqual(proposal['reason'],'node.blocked')
        self.assertNotEqual((proposal['after']['x'],proposal['after']['y']),(0,0))
    def test_draft_with_no_route_nodes_remains_editable(self):
        self.scene['nodes']=[];self.scene['portals'][0]['b']=None
        out=preview_editor(self.scene)
        self.assertEqual(len(out['floors']),2);self.assertEqual(out['legs'],[])
        self.assertEqual(out['preflight']['portals'][0]['state'],'incomplete')
    def test_duplicate_ids_and_nonfinite_coordinates_rejected(self):
        for value in (float('nan'),float('inf'),True,2.2):
            s=copy.deepcopy(self.scene);s['portals'][0]['a']['x']=value
            with self.assertRaises(ValueError):preflight_editor(s)
        self.scene['portals'][1]['id']=self.scene['portals'][0]['id']
        with self.assertRaises(ValueError):preflight_editor(self.scene)
    def test_label_text_not_used_to_infer_connectivity(self):
        # Similar labels on unpaired pins do not create a link.
        self.scene['portals']=[{'id':'Ea_F1','a':{'floor':'F1','x':20,'y':80},'b':None},
                               {'id':'Ea_F2','a':{'floor':'F2','x':20,'y':80},'b':None}]
        self.assert_blocked_before_search(self.scene)

class I18nTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.messages=json.loads((ROOT/'web/locales.json').read_text())
    def test_identical_nonempty_keys_and_placeholders(self):
        en,zh=self.messages['en'],self.messages['zh-Hant']
        self.assertEqual(set(en),set(zh))
        for k in en:
            with self.subTest(key=k):
                self.assertTrue(en[k] and zh[k])
                self.assertEqual(set(re.findall(r'\{(\w+)\}',en[k])),set(re.findall(r'\{(\w+)\}',zh[k])))
    def test_all_html_keys_exist_and_english_initial_page(self):
        html=(ROOT/'web/editor.html').read_text()
        self.assertIn('lang="en"',html)
        for key in re.findall(r'data-i18n(?:-[\w-]+)?="([\w.]+)"',html):self.assertIn(key,self.messages['en'])
    def test_javascript_has_no_hardcoded_chinese_ui(self):
        for f in ('editor.js','portal-editor.js'):
            self.assertFalse(re.search('[\u4e00-\u9fff]',(ROOT/'web'/f).read_text()),f)
    def test_structured_error_switch_retains_user_names(self):
        exc=SceneIssues([dict(code='portal.missing',params={'endpoint':'Ea_2F'},severity='error')])
        payload=exception_payload(exc)
        en=localize_payload(payload,'en');zh=localize_payload(payload,'zh-TW')
        self.assertNotEqual(en['error'],zh['error'])
        self.assertEqual(en['error_code'],zh['error_code'])
        self.assertEqual(en['issues'],zh['issues'])
    def test_changing_language_never_localizes_scene_or_result(self):
        data={'phase':'GA 進化中','scene':{'id':'保留使用者名稱'},'result':{'loss':25.2}}
        for lang in ('en','zh-Hant'):
            value=localize_payload(data,lang)
            self.assertEqual(value['scene'],data['scene']);self.assertEqual(value['result'],data['result'])
    def test_numeric_errors_and_phases_are_actionable(self):
        en=localize_payload(exception_payload(ValueError('radius 必須介於 0–2。')),'en')
        self.assertEqual(en['error_code'],'error.field_range');self.assertIn('radius',en['error'])
        self.assertEqual(localize_payload({'phase':'GA 進化中'},'en')['phase'],'Evolving GA populations')

class PortalHTTPTests(HTTPTests):
    def test_preflight_allows_editing_but_job_rejects_missing_end(self):
        scene=editor_demo();scene['portals'][0]['b']=None
        code,body=self.request('/api/editor/preflight',scene)
        self.assertEqual(code,200);self.assertFalse(json.loads(body)['ok'])
        code,body=self.request('/api/editor/preview',scene)
        self.assertEqual(code,200);v=json.loads(body);self.assertFalse(v['legs']);self.assertEqual(v['error_code'],'validation.preflight')
        from app import editor_jobs
        before=set(editor_jobs.items)
        for lang in ('en','zh-Hant'):
            code,body=self.request('/api/editor/jobs',scene,**{'Accept-Language':lang})
            self.assertEqual(code,400);v=json.loads(body)
            self.assertEqual(v['error_code'],'validation.links');self.assertTrue(v['issues'])
            self.assertEqual(set(editor_jobs.items),before)
            if lang=='en':self.assertFalse(re.search('[\u4e00-\u9fff]',v['error']))
            else:self.assertTrue(re.search('[\u4e00-\u9fff]',v['error']))
    def test_shared_locale_assets_and_csp(self):
        for path in ('/messages.js','/i18n.js','/portal-editor.js'):
            self.assertEqual(self.request(path)[0],200)
        # Do not weaken production CSP to enable translations.
        self.assertNotIn("unsafe-eval",(ROOT/'app.py').read_text())
    def test_invalid_requests_are_english_by_default(self):
        code,body=self.request('/api/editor/jobs',{'schema_version':99})
        self.assertEqual(code,400);self.assertEqual(json.loads(body)['error_code'],'error.schema')
        code,body=self.request('/api/map-preview',{'map_data':'garbage'},**{'Accept-Language':'zh-Hant'})
        self.assertEqual(code,400);self.assertEqual(json.loads(body)['error_code'],'error.image')

if __name__=='__main__':unittest.main()
