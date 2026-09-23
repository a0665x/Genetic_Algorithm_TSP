import base64
from io import BytesIO
import itertools
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from scipy.ndimage import label
from scheduler.map_import import (review_map, classify, options_from, reduce_classes,
                                  WALL, UNKNOWN, COST, FREE, MapImportError, reference_maps)
from scheduler.core import Costmap
from scheduler.editor import editor_demo, preflight_editor, preview_editor
from scheduler.messages import exception_payload, localize_payload

ROOT=Path(__file__).resolve().parents[1]
def encoded(image):
    b=BytesIO();image.save(b,format='PNG');return base64.b64encode(b.getvalue()).decode()
def request(image, **kw):return review_map(dict(map_data=encoded(image),**kw))
def decoded(url):return np.asarray(Image.open(BytesIO(base64.b64decode(url.split(',')[-1]))))

class MapImportTests(unittest.TestCase):
    def test_auto_unknown_205_and_217_blocked_white_free(self):
        a=np.full((40,60),205,np.uint8);a[5:35,6:30]=254;a[10:20,35:55]=217;a[15:25,10]=0
        r=request(Image.fromarray(a),settings={'radius':0})
        self.assertEqual(r['analysis']['profile'],'lidar')
        p=decoded(r['map_data']);self.assertEqual(p[20,45],0);self.assertEqual(p[2,2],0);self.assertEqual(p[8,8],255);self.assertEqual(p[20,10],0)
    def test_gray_walkable_is_explicit_not_default(self):
        a=np.full((20,20),205,np.uint8)
        self.assertEqual(request(Image.fromarray(a))['stats']['walkable'],0)
        r=request(Image.fromarray(a),options={'profile':'floorplan'},settings={'radius':0})
        self.assertEqual(int(decoded(r['map_data'])[5,5]),200)
        self.assertGreater(r['stats']['walkable'],0)
    def test_color_annotations_are_unknown(self):
        im=Image.new('RGB',(12,12),(250,250,210))
        self.assertEqual(request(im)['stats']['walkable'],0)
    def test_transparency_overrides_free_color_rule(self):
        im=Image.new('RGBA',(12,12),(255,255,255,254))
        r=request(im,options={'profile':'custom','rules':[{'color':'#ffffff','kind':'free','tolerance':0}]})
        self.assertEqual(r['stats']['walkable'],0)
    def test_custom_color_tolerance_and_overlap_precedence(self):
        im=Image.new('RGB',(12,12),(19,119,219))
        rules=[{'color':'#1478dc','kind':'free','tolerance':1}]
        self.assertGreater(request(im,options={'profile':'custom','rules':rules})['stats']['walkable'],0)
        rules.append({'color':'#1478dc','kind':'wall','tolerance':2})
        for rr in (rules,rules[::-1]):self.assertEqual(request(im,options={'profile':'custom','rules':rr})['stats']['walkable'],0)
    def test_unmatched_custom_color_stays_unknown(self):
        self.assertEqual(request(Image.new('RGB',(12,12),'white'),options={'profile':'custom'})['stats']['walkable'],0)
    def test_invert_black_floor(self):
        im=Image.new('L',(20,20),0)
        self.assertEqual(request(im)['stats']['walkable'],0)
        self.assertGreater(request(im,options={'invert':True})['stats']['walkable'],0)
    def test_min_pool_never_erases_one_pixel_wall(self):
        a=np.full((64,1024),255,np.uint8);a[:,511]=0
        r=request(Image.fromarray(a),source_resolution=.05,settings={'radius':0})
        self.assertEqual(r['factor'],2);self.assertEqual(r['resolution'],.1)
        p=decoded(r['map_data']);self.assertTrue(np.all(p[:,255]==0))
        with self.assertRaises(ValueError):Costmap(p,.1,radius=0).astar((10,10),(500,10))
    def test_nondivisible_padding_unknown_and_consistent_scale(self):
        r=request(Image.new('L',(1025,91),255),source_resolution=.03,settings={'radius':0})
        self.assertEqual(r['factor'],3);self.assertEqual((r['width'],r['height']),(342,31))
        p=decoded(r['map_data']);self.assertTrue(np.all(p[:,-1]==0));self.assertTrue(np.all(p[-1,:]==0))
        self.assertAlmostEqual(r['resolution'],.09)
    def test_class_precedence_in_block_reduction(self):
        for xs in itertools.product(range(4),repeat=4):
            result=reduce_classes(np.array(xs,np.uint8).reshape(2,2),2)
            self.assertEqual(result[0,0],min(xs))
    def test_review_clearance_matches_real_costmap(self):
        a=np.full((80,80),255,np.uint8);a[20:50,40]=0;a[10:20,10:20]=210
        r=request(Image.fromarray(a),options={'profile':'floorplan'},source_resolution=.15,settings={'radius':.3,'threshold':220})
        grid=Costmap(decoded(r['map_data']),r['resolution'],radius=.3,threshold=220)
        self.assertEqual(r['blocked_rows'],[''.join('1' if x else '0' for x in row) for row in grid.blocked])
    def test_exact_source_sample_and_bounds(self):
        im=Image.new('RGB',(20,20),(205,205,205));im.putpixel((7,9),(1,2,3))
        r=request(im,sample={'x':7,'y':9});self.assertEqual(r['color'],'#010203')
        with self.assertRaises(MapImportError):request(im,sample={'x':20,'y':9})
    def test_invalid_inputs(self):
        for opts in [{'profile':'nonsense'},{'invert':'true'},{'free_threshold':10,'wall_threshold':100}, {'max_side':600},{'max_side':True},{'rules':None},{'rules':[{'color':'#xx','kind':'free'}]},{'rules':[{'color':'#ffffff','kind':'open'}]}]:
            with self.subTest(opts=opts),self.assertRaises(MapImportError):request(Image.new('L',(20,20)),options=opts)
        for raw in [None,False,'junk']:
            with self.assertRaises(MapImportError):review_map({'map_data':raw})
        with self.assertRaises(MapImportError):request(Image.new('L',(8200,4)))
        with self.assertRaises(MapImportError):request(Image.new('L',(1024,64)),source_resolution=2)
    def test_typed_errors_localize_to_both_languages(self):
        exc=MapImportError('threshold_order')
        en=localize_payload(exception_payload(exc),'en');zh=localize_payload(exception_payload(exc),'zh-Hant')
        self.assertIn('greater',en['error']);self.assertIn('大於',zh['error']);self.assertEqual(en['error_code'],zh['error_code'])
    def test_import_does_not_search_or_create_ga(self):
        with patch('scheduler.core.Costmap.astar',side_effect=AssertionError),patch('scheduler.editor.evolve',side_effect=AssertionError):
            request(Image.new('L',(20,20),255))

class RepositoryMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maps={}
        for p in (ROOT/'data/reference_maps').glob('map_*.png'):
            cls.maps[p.stem]=review_map(dict(map_data=base64.b64encode(p.read_bytes()).decode(),source_resolution=.1))
    def test_pinned_reference_bytes_and_all_have_usable_regions(self):
        import hashlib
        p=ROOT/'data/reference_maps'
        for f in json.loads((p/'provenance.json').read_text())['files']:
            raw=(p/f['file']).read_bytes();self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),f['git_blob_sha'])
        self.assertEqual(len(reference_maps()),3)
        for r in self.maps.values():self.assertGreater(r['stats']['largest_component'],100)
    def test_real_source_wall_and_unknown_pixels_remain_blocked_after_reduction(self):
        for name,r in self.maps.items():
            im=Image.open(ROOT/'data/reference_maps'/f'{name}.png').convert('RGBA')
            c,_=classify(im,options_from({}));source_blocked=c<=UNKNOWN
            p=decoded(r['map_data'])
            reduced=reduce_classes(c,r['factor'])
            self.assertTrue(np.all(p[reduced<=UNKNOWN]==0))
    def test_real_map_astar_path_has_no_unknown_or_wall(self):
        r=self.maps['map_1'];g=Costmap(decoded(r['map_data']),r['resolution'],radius=.2)
        cc,_=label(~g.blocked);counts=np.bincount(cc.ravel());c=int(np.argmax(counts[1:])+1)
        ys,xs=np.where(cc==c);a=(int(xs[0]),int(ys[0]));b=(int(xs[-1]),int(ys[-1]))
        path,_,_=g.astar(a,b)
        self.assertTrue(all(g.valid(p) and g.pixels[p[1],p[0]]>100 for p in path))
    def test_two_real_maps_require_explicit_portals(self):
        scene=editor_demo();scene['nodes']=[];scene['portals']=[];scene['floors']=[]
        points=[]
        for i,r in enumerate([self.maps['map_1'],self.maps['map_6']],1):
            fid=f'{i}F';scene['floors'].append(dict(id=fid,name=fid,map_data=r['map_data'],resolution=r['resolution']))
            a=np.array([list(s) for s in r['blocked_rows']])=='0';cc,_=label(a);counts=np.bincount(cc.ravel());c=int(np.argmax(counts[1:])+1);ys,xs=np.where(cc==c);k=len(xs)//2
            points.append(dict(floor=fid,x=int(xs[k]),y=int(ys[k])))
        scene['nodes']=[dict(id='S',**points[0]),dict(id='G',**points[1])]
        self.assertFalse(preflight_editor(scene)['ok'])
        scene['portals']=[dict(id='Ea',a=points[0],b=points[1],enabled=True,wait=15,door=6,ride=8,reverse_wait=20)]
        self.assertTrue(preflight_editor(scene)['ok'])
        self.assertTrue(any(s['kind']=='elevator' for l in preview_editor(scene)['legs'] for s in l['segments']))
        scene['portals'][0]['b']=dict(floor='2F',x=None,y=None)
        self.assertFalse(preflight_editor(scene)['ok'])
