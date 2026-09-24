"""Sheet presentation does not mutate metric routing or elevator connectivity."""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

import numpy as np
from app import Handler
from scheduler.editor import starter_scene, editor_demo, preview_editor, validate_editor
from scheduler.building import prepare_building


class SheetModelTests(unittest.TestCase):
    def test_start_is_one_blank_sheet_without_tasks_or_elevators(self):
        s = starter_scene()
        self.assertEqual(s['schema_version'], 3)
        self.assertEqual(len(s['floors']), 1)
        self.assertEqual(s['nodes'], [])
        self.assertEqual(s['portals'], [])
        view = preview_editor(s)
        self.assertTrue(view['preflight']['ok'])
        self.assertEqual(view['legs'], [])
        self.assertEqual(view['distance'], 0)

    def test_default_and_demo_are_independent(self):
        a = starter_scene(); a['settings']['seed'] = 1
        a['floors'][0]['name'] = 'changed'
        b = starter_scene()
        self.assertNotEqual(b['settings']['seed'], 1)
        self.assertEqual(b['floors'][0]['name'], 'Sheet 1')
        self.assertEqual(len(editor_demo()['floors']), 2)

    def test_sheet_stack_order_does_not_change_time_or_distance(self):
        s = editor_demo()
        base = prepare_building(validate_editor(s))
        s['floors'].reverse()
        after = prepare_building(validate_editor(s))
        np.testing.assert_array_equal(base['distance'], after['distance'])
        np.testing.assert_array_equal(base['travel'], after['travel'])
        self.assertEqual(base['segments'], after['segments'])

    def test_skipping_a_display_sheet_does_not_create_an_elevator_stop(self):
        s = starter_scene(); f = s['floors'][0]
        s['floors'] = [dict(f, id=f'S{i}', name=f'Sheet {i}') for i in (1, 2, 3)]
        s['nodes'] = [dict(id='Start',floor='S1',x=40,y=80),
                      dict(id='End',floor='S3',x=80,y=80)]
        s['portals'] = [dict(id='Ea', a=dict(floor='S1',x=60,y=80),
                             b=dict(floor='S3',x=60,y=80), enabled=True)]
        result = preview_editor(s)
        self.assertIsNone(result['error'])
        steps = result['legs'][0]['segments']
        self.assertFalse(any(step.get('floor') == 'S2' for step in steps))
        elevators = [step for step in steps if step['kind']=='elevator']
        self.assertEqual(len(elevators),1)
        self.assertEqual(elevators[0]['end']['floor'],'S3')
        s['nodes'][-1]['floor'] = 'S2'
        self.assertFalse(preview_editor(s)['preflight']['ok'])

    def test_empty_or_removed_endpoint_never_becomes_a_node(self):
        s = starter_scene()
        s['portals'] = [dict(id='Ea', a=dict(floor='sheet-1',x=30,y=30),
                             b=dict(floor='deleted-sheet',x=None,y=None),enabled=True)]
        v = preview_editor(s)
        self.assertFalse(v['preflight']['ok'])
        self.assertEqual(v['legs'],[])
        self.assertEqual(s['nodes'],[])

    def test_new_language_keys_have_matching_placeholders(self):
        from pathlib import Path
        import re
        catalogue = json.loads((Path(__file__).parents[1]/'web/locales.json').read_text())
        for key in catalogue['en']:
            self.assertIn(key, catalogue['zh-Hant'])
            self.assertEqual(set(re.findall(r'\{\w+\}',catalogue['en'][key])),
                             set(re.findall(r'\{\w+\}',catalogue['zh-Hant'][key])), key)


class SheetHTTPTests(unittest.TestCase):
    def test_start_and_workbench_assets_are_served(self):
        server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base = f'http://127.0.0.1:{server.server_address[1]}'
        try:
            with urlopen(base+'/api/editor/start') as r:
                s=json.load(r)
            self.assertEqual(len(s['floors']),1)
            self.assertEqual(s['nodes'],[])
            for path in ('/sheet-workbench.js','/sheet-workbench.css','/'):
                with urlopen(base+path) as r:
                    self.assertEqual(r.status,200)
                    self.assertTrue(r.read())
                    self.assertNotIn('unsafe-eval',r.headers['Content-Security-Policy'])
        finally:
            server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
