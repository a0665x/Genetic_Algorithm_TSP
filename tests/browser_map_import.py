"""Real image import acceptance checks. Native HTTP by default; optional DOM harness."""
import argparse
import json
from pathlib import Path
import re
import sys
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import numpy as np
from scipy.ndimage import label
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import Handler

def run():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--offline-harness',action='store_true');parser.add_argument('--chromium');args=parser.parse_args()
    out=ROOT/'test-artifacts';out.mkdir(exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_address[1]}'
    checks=[];errors=[];calls=[]
    def http(path,data=None,language='en'):
        assert path.startswith('/api/')
        calls.append(path);req=Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json','Accept-Language':language})
        try:
            with urlopen(req,timeout=60) as r:return dict(ok=True,status=r.status,value=json.load(r))
        except HTTPError as e:return dict(ok=False,status=e.code,value=json.load(e))
    def safe_positions(rows):
        a=np.array([list(s) for s in rows])=='0';cc,_=label(a);sizes=np.bincount(cc.ravel());c=int(np.argmax(sizes[1:])+1);ys,xs=np.where(cc==c)
        return [(int(xs[i]),int(ys[i])) for i in [len(xs)//4,len(xs)//2,3*len(xs)//4]]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=args.chromium);page=browser.new_page(viewport=dict(width=1440,height=1100))
            page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept());page.on('request',lambda r:calls.append(r.url.removeprefix(base)))
            if args.offline_harness:
                page.expose_function('harnessHttp',http);page.set_content(re.sub(r'<link[^>]+>|<script[^>]+></script>','',(ROOT/'web/editor.html').read_text()))
                for name in ['studio.css','editor.css','map-import.css']:page.add_style_tag(content=(ROOT/'web'/name).read_text())
                page.evaluate('''() => {window.fetch=async(path,opts={})=>{const r=await window.harnessHttp(path,opts.body?JSON.parse(opts.body):null,opts.headers?.['Accept-Language']||'en');return {ok:r.ok,status:r.status,json:async()=>r.value};};}''')
                page.evaluate('(v)=>window.DISPATCH_MESSAGES=v',json.loads((ROOT/'web/locales.json').read_text()))
                for name in ['i18n.js','editor.js','portal-editor.js','map-import.js']:page.add_script_tag(content=(ROOT/'web'/name).read_text())
            else:page.goto(base)
            def ev(expr):return page.evaluate('() => '+expr)
            def wait(expr):page.wait_for_function('() => '+expr,timeout=60000)
            def ready():wait('preview && !previewRunning && !previewQueued')
            def check(name,ok):assert ok,name;checks.append(name);print('PASS:',name,flush=True)
            def shot(name):page.screenshot(path=str(out/(name+'.png')),full_page=True)
            def settings():page.click('#settingsBtn');wait('draftPreflight!==null')
            def save():page.click('#applySettingsBtn');wait('!document.getElementById("settingsDialog").open');ready()
            def point(fid,x,y):
                q=page.evaluate('(p)=>project(p)',dict(floor=fid,x=x+.5,y=y+.5));b=page.locator('#mapCanvas').bounding_box();return b['x']+q['x'],b['y']+q['y']
            ready();original=ev('exported()');empty=json.loads(json.dumps(original));empty['nodes']=[];empty['portals']=[];empty['floors']=empty['floors'][:1]
            page.set_input_files('#importFile',dict(name='empty-scene.json',mimeType='application/json',buffer=json.dumps(empty).encode()));wait('scene.nodes.length===0');ready()
            settings();wait('document.getElementById("referenceMapSelect").options.length===3')
            check('three pinned source-map examples available',page.locator('#referenceMapSelect option').count()==3)
            page.click('#loadReferenceMap');wait('mapReview!==null && !mapReading')
            check('reference picker uses real image data',ev('mapReview.source_size[0]===1696 && mapReview.factor===4'))
            page.click('#closeMapImport');check('cancel does not mutate floor data',ev('draft.floors.length===1'))
            page.click('#addFloorBtn');page.set_input_files('#floorUpload',[str(ROOT/'data/reference_maps/map_1.png'),str(ROOT/'data/reference_maps/map_2.png')]);wait('mapReview!==null && !mapReading')
            check('large source gets conservative review, not silent upload',page.locator('#applyMapImport').is_disabled() and ev('draft.floors.length===1 && mapReview.width===424 && mapReview.analysis.profile==="lidar"'))
            page.fill('#mapFloorId','L1');page.fill('#mapFloorName','Level 1');page.fill('#mapScale','0.05');page.locator('#mapScale').press('Tab');wait('mapReview!==null && !mapReading && mapReview.resolution===.2')
            check('scale changes by the exact integer reduction factor',ev('mapReview.resolution===.2 && mapReview.factor===4'))
            page.click('#mapAdvanced > summary');page.click('#pickMapColor')
            rect=page.locator('#sourceCanvas').bounding_box();page.mouse.click(rect['x']+rect['width']*.5,rect['y']+rect['height']*.02);wait('!mapPicking')
            check('eyedropper samples the exact source gray',page.locator('#mapColor').input_value()=='#cdcdcd')
            page.select_option('#mapRuleKind','cost');page.click('#addMapRule');wait('mapReview!==null && !mapReading')
            check('manual rule changes real backend classes',ev('mapReview.stats.counts.cost>100'))
            page.click('#mapRules button');wait('mapReview!==null && !mapReading')
            check('removing rule restores blocked unknown background',ev('mapReview.stats.counts.cost===0 && mapReview.stats.counts.unknown>1000'))
            snapshot=ev('JSON.stringify({options:mapReview.options,stats:mapReview.stats})')
            page.select_option('#mapLanguage','zh-Hant');check('import dialog translates to Traditional Chinese', '原圖' in page.locator('#mapImportDialog').inner_text() and '確認' in page.locator('#mapImportDialog').inner_text())
            check('translation does not change classification',ev('JSON.stringify({options:mapReview.options,stats:mapReview.stats})')==snapshot)
            page.select_option('#mapLanguage','en');page.click('#mapAdvanced > summary');shot('semantic-review')
            page.select_option('#reviewLayer','clearance_preview');check('inflation preview selectable',page.locator('#reviewLayer').input_value()=='clearance_preview')
            page.check('#mapReviewed');page.click('#applyMapImport');wait('mapCandidate && mapCandidate.name==="map_2.png" && mapReview!==null && !mapReading')
            check('batch import requires a review of each image',ev('draft.floors.length===2') and not page.locator('#mapReviewed').is_checked())
            page.fill('#mapFloorId','L2');page.fill('#mapFloorName','Level 2');page.fill('#mapScale','0.05');page.locator('#mapScale').press('Tab');wait('mapReview!==null && !mapReading && mapReview.resolution===.2');page.check('#mapReviewed');page.click('#applyMapImport');wait('!document.getElementById("mapImportDialog").open')
            page.locator('.floor-setting[data-floor="F1"] .removeFloor').click();save()
            check('two imported source maps become independently labeled floors',ev('scene.floors.length===2 && scene.floors[0].id==="L1" && scene.floors[1].id==="L2" && scene.floors.every(f=>f.semantics.source_sha256)'))
            points={f['id']:safe_positions(f['blocked_rows']) for f in ev('floors')}
            snapshot=ev('JSON.stringify(exported())');page.select_option('#mapLayer','classes');page.click('#structureBtn');shot('semantic-floors')
            page.select_option('#mapLayer','original');check('display layers leave scene and routing masks unchanged',ev('JSON.stringify(exported())')==snapshot);page.select_option('#mapLayer','planning')
            settings();page.click('#addPortalBtn');card=page.locator('.portal-setting[data-portal="Ea"] .endpoint-card[data-side="a"]');card.locator('.placeEndpoint').click();wait('portalPick!==null');ready();page.mouse.click(*point('L1',*points['L1'][1]));ready();page.click('#structureBtn')
            check('half elevator on imported rasters blocks routing',ev('portalRenderState.some(p=>p.kind==="half") && preview.preflight.ok===false'))
            shot('semantic-half-link');settings();card=page.locator('.portal-setting[data-portal="Ea"] .endpoint-card[data-side="b"]');card.locator('.placeEndpoint').click();wait('portalPick!==null');ready();page.mouse.click(*point('L2',*points['L2'][1]));ready()
            check('pair is connected only after both real map endpoints are placed',ev('preview.preflight.ok && scene.portals[0].a.floor==="L1" && scene.portals[0].b.floor==="L2"'))
            for fid,pos in [('L1',points['L1'][0]),('L1',points['L1'][2]),('L2',points['L2'][2])]:
                page.click('[data-floor="'+fid+'"]');page.mouse.click(*point(fid,*pos),button='right');page.click('#contextAdd');ready()
            check('pre-GA route uses explicit elevator on actual imported map masks',ev('preview.legs.length===2 && preview.legs.some(l=>l.segments.some(s=>s.kind==="elevator"))'))
            page.click('#planBtn');wait('result!==null && !busy');check('GA completes on the two imported maps',ev('Number.isFinite(result.best.loss) && meta.labels.length===3'))
            page.click('#structureBtn');shot('semantic-planned')
            saved=ev('exported()');page.set_input_files('#importFile',dict(name='roundtrip.json',mimeType='application/json',buffer=json.dumps(saved).encode()));ready()
            check('scene roundtrip preserves originals, rules, physical scale and endpoints',ev('JSON.stringify(exported().floors)')==json.dumps(saved['floors'],ensure_ascii=False,separators=(',',':')) and ev('scene.portals[0].b.floor==="L2"'))
            settings();field=page.locator('.floor-setting[data-floor="L1"] .floor-id-input');field.fill('B1');field.press('Tab');wait('draft.floors[0].id==="B1"');save()
            check('floor rename updates nodes and elevator references atomically',ev('scene.nodes[0].floor==="B1" && scene.portals[0].a.floor==="B1" && preview.preflight.ok'))
            settings();page.locator('.floor-setting[data-floor="B1"] .editSemantics').click();wait('mapReview!==null && !mapReading');check('saved source can be reclassified without image re-upload',ev('mapReview.source_sha256===scene.floors[0].semantics.source_sha256'))
            page.set_viewport_size(dict(width=390,height=844));check('mobile import dialog has no page overflow',ev('document.documentElement.scrollWidth<=innerWidth+2'));shot('semantic-mobile')
            check('no untranslated application keys',ev('I18n.missing.size===0'));check('no JavaScript errors',not errors)
            report=dict(mode='DOM-to-real-HTTP harness' if args.offline_harness else 'native browser HTTP',passed=len(checks),checks=checks,errors=errors)
            (out/'semantic-browser-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));browser.close()
    finally:server.shutdown();server.server_close()

if __name__=='__main__':run()
