"""Real-browser editor acceptance checks. Optional isolated DOM-to-HTTP harness.

Run without --offline-harness for native HTTP/CSP validation. The harness verifies
local DOM/Canvas actions against the real API, not browser networking.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import Handler


def run():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--offline-harness', action='store_true')
    ap.add_argument('--chromium', default=None)
    ap.add_argument('--initial-only', action='store_true')
    args = ap.parse_args()
    out = ROOT/'test-artifacts'; out.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_address[1]}'
    checks=[]; errors=[]; requests=[]; frames=[]
    def http(path, data=None, language='en'):
        if not isinstance(path,str) or not path.startswith('/api/'):
            raise ValueError('Only local API paths are allowed')
        req=Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json','Accept-Language':language})
        try:
            with urlopen(req,timeout=60) as r:return dict(ok=True,status=r.status,value=json.load(r))
        except HTTPError as e:return dict(ok=False,status=e.code,value=json.load(e))
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=args.chromium)
            page=browser.new_page(viewport=dict(width=1440,height=1450),device_scale_factor=1)
            page.on('pageerror',lambda e:(errors.append(str(e)),print('JS ERROR:',e,flush=True)))
            page.on('request',lambda r:requests.append(r.url))
            if args.offline_harness:
                page.expose_function('harnessHttp',http)
                html=re.sub(r'<link[^>]+>|<script[^>]+></script>','',(ROOT/'web/editor.html').read_text())
                page.set_content(html)
                for f in ['studio.css','editor.css','map-import.css']:page.add_style_tag(content=(ROOT/'web'/f).read_text())
                page.evaluate("""() => {window.fetch=async(path,opts={})=>{const r=await window.harnessHttp(path,opts.body?JSON.parse(opts.body):null,opts.headers?.['Accept-Language']||'en');return {ok:r.ok,status:r.status,json:async()=>r.value};};}""")
                page.evaluate('(data)=>{window.DISPATCH_MESSAGES=data;}', json.loads((ROOT/'web/locales.json').read_text()))
                for asset in ('i18n.js','editor.js','portal-editor.js','map-import.js'):page.add_script_tag(content=(ROOT/'web'/asset).read_text())
            else:
                page.goto(base)
            page.set_default_timeout(15000)
            def wait(expr):page.wait_for_function('() => '+expr,timeout=30000)
            def check(name, condition):
                assert condition, name
                checks.append(name);print('PASS:',name,flush=True)
            def ev(expr):return page.evaluate('() => '+expr)
            def snapshot(name):
                path=out/f'{name}.png';page.screenshot(path=str(path),full_page=True);frames.append(path)
            def ready():wait('preview && !previewRunning && !previewQueued')
            def position(floor,x,y,head=False):
                q=page.evaluate('(p)=>project(p)',dict(floor=floor,x=x+.5,y=y+.5))
                b=page.locator('#mapCanvas').bounding_box()
                return b['x']+q['x'], b['y']+q['y']-(20 if head else 0)
            def drag(a,b):
                page.mouse.move(*a);page.mouse.down();page.mouse.move(*b,steps=10);page.mouse.up()
            ready()
            original=ev('exported()')
            check('unavailable map coordinates fail safely',ev('validPoint(null) === false && validPoint({floor:"missing",x:0,y:0}) === false'))
            check('A* preview before any GA',ev('preview.legs.length===7 && meta===null && history.length===0'))
            check('automatic cross-floor elevator in preview',ev('preview.legs.some(l=>l.segments.some(s=>s.kind==="elevator"))'))
            check('endpoint roles and collapsed math',page.locator('.route-item.start').count()==1 and page.locator('.route-item.end').count()==1 and not page.locator('#calculationPanel').is_visible())
            snapshot('editor-preview')
            if args.initial_only:
                print(json.dumps(dict(checks=checks,errors=errors),ensure_ascii=False));return
            page.click('#structureBtn');snapshot('editor-structure');page.click('[data-floor="F1"]')
            # Real location-pin drag; no direct scene mutation.
            drag(position('F1',20,20,True),position('F1',22,22,True))
            ready()
            check('pin drag changes coordinates and preview',ev('scene.nodes[1].x===22 && scene.nodes[1].y===22 && preview.legs[0].segments.at(-1).path.at(-1)[0]===22'))
            drag(position('F1',22,22,True),position('F1',0,0,True))
            check('wall drop rolls back',ev('scene.nodes[1].x===22 && scene.nodes[1].y===22'))
            # Context-menu addition on an actual map coordinate.
            page.mouse.click(*position('F1',85,112),button='right');page.click('#contextAdd');ready()
            check('right-click add becomes red endpoint',ev('scene.nodes.at(-1).x===85 && scene.nodes.at(-1).y===112') and page.locator('.route-item.end').inner_text().find('N1')>=0)
            page.click('#undoBtn');ready()
            # Left toolbar addition then deletion.
            page.click('#addBtn');page.mouse.click(*position('F1',85,112));ready();page.keyboard.press('Escape')
            check('left add tool creates node',ev('scene.nodes.length===9'))
            page.click('#deleteBtn');ready();check('left delete tool removes selection',ev('scene.nodes.length===8'))
            # Reorder via a real HTML drag/drop, including an endpoint role change.
            first=page.locator('.route-item').nth(1)
            key=first.get_attribute('data-key')
            await_target=page.locator('.route-item').nth(0)
            first.locator('.grip').drag_to(await_target,target_position={'x':80,'y':3})
            ready();check('right list drag changes first node/start role',ev('scene.nodes[0].id==="A"') and page.locator('.route-item.start').get_attribute('data-key')==key)
            snapshot('editor-reordered')
            page.click('#undoBtn');ready()
            # Explicit start/end selectors.
            endkey=ev('scene.nodes[2]._key');page.select_option('#endSelect',endkey);ready()
            check('endpoint selector changes last node',ev('scene.nodes.at(-1).id==="B"'))
            page.click('#undoBtn');ready()
            # Marquee around two upper-room nodes, context delete and undo.
            page.click('[data-floor="F1"]')
            a=position('F1',10,5);b=position('F1',110,28)
            drag(a,b)
            check('marquee selects multiple pins',ev('selection.size===2'))
            page.mouse.click(*position('F1',70,42),button='right');page.click('#contextDelete');ready()
            check('context batch delete updates endpoint list',ev('scene.nodes.length===6'))
            page.click('#undoBtn');ready()
            # Right-click just one node for individual deletion.
            page.mouse.click(*position('F1',22,22,True),button='right');page.click('#contextDelete');ready()
            check('right-click single delete',ev('!scene.nodes.some(n=>n.id==="A")'))
            page.click('#undoBtn');ready()
            # UI minute conversion and safe names.
            page.locator('.route-item').nth(1).click();page.fill('#waited','2.5');page.locator('#waited').press('Tab');ready()
            check('wait minutes convert to seconds',ev('scene.nodes[1].waited===150'))
            page.fill('#nodeName','<img onerror=bad>');page.locator('#nodeName').press('Tab');ready()
            check('names are escaped',page.locator('#routeList img').count()==0)
            page.fill('#nodeName','A');page.locator('#nodeName').press('Tab');ready()
            # Pre-GA preview has no W/result. GA produces actual elite/migration data.
            page.click('#planBtn');wait('result!==null && !busy')
            check('fixed endpoints survive every GA generation',ev('history.every(h=>h.worlds.every(w=>w.route[0]===0 && w.route.at(-1)===scene.nodes.length-1))'))
            check('41 generations with actual retained elites',ev('history.length===41 && history.every(h=>h.worlds.every(w=>w.elites.length>0 && w.elites[0].loss===w.loss))'))
            check('SAW migrations reported',ev('history.some(h=>h.transfers.length>0)'))
            check('backend loss shown',abs(float(page.locator('#loss').inner_text())-ev('displayRecord().loss'))<.01)
            check('weight matrix opens automatically after GA',page.locator('#matrixTable').is_visible() and not page.locator('#formulaDetails').get_attribute('open'))
            page.click('#weightPanel > summary')
            snapshot('editor-evolution')
            page.locator('#generation').evaluate('(e)=>{e.value=10;e.dispatchEvent(new Event("input"));}')
            check('iteration selector links route and migration',ev('activeRecord().route.join()===history[10].worlds[history[10].best_world-1].route.join()') and '10' in page.locator('#iteration').inner_text())
            page.uncheck('#evolutionToggle')
            check('evolution off freezes final route',ev('displayRecord()===activeRecord(history.length-1)') and page.locator('#generation').is_disabled())
            page.check('#evolutionToggle');page.click('#playBtn');wait('Number(document.getElementById("generation").value)>0');page.click('#playBtn')
            check('playback advances generations',ev('Number(document.getElementById("generation").value)>0 && !replayTimer'))
            page.locator('#generation').evaluate('(e)=>{e.value=e.max;e.dispatchEvent(new Event("input"));}')
            page.click('#weightPanel > summary');page.click('#formulaDetails > summary')
            check('real W and formulas only after GA',page.locator('#matrixTable tbody tr').count()==8 and page.locator('#weightDetails tbody tr').count()==6 and page.locator('.equation').count()==8)
            snapshot('editor-math')
            page.click('#formulaDetails > summary');page.click('#weightPanel > summary')
            # Single world switch invalidates all obsolete GA results, not just text.
            page.uncheck('#sawToggle');ready()
            check('edits clear stale GA and weights',ev('meta===null && result===null && history.length===0') and not page.locator('#calculationPanel').is_visible())
            page.click('#planBtn');wait('result!==null && !busy')
            check('SAW off is truly single world',ev('history.every(h=>h.worlds.length===1 && h.transfers.length===0) && result.events.length===0'))
            check('header elevator list matches actual GA segments',ev('document.getElementById("previewElevators").textContent === (activeSegments().filter(s=>s.kind==="elevator").map(s=>`${s.id} ${s.start.floor} → ${s.end.floor}`).join(" / ") || t("route.same_floor"))'))
            bestnames=ev('displayRecord().route.map(i=>scene.nodes[i].id)')
            page.click('#applyBestBtn');ready();check('adopt selected solution updates editable order',ev('scene.nodes.map(n=>n.id)')==bestnames)
            # Import/export roundtrip, empty editor, two endpoints, unreachable preview.
            def load(s):
                before=ev('revision')
                page.set_input_files('#importFile',dict(name='scene.json',mimeType='application/json',buffer=json.dumps(s).encode()))
                wait(f'revision > {before}');ready()
            load(original);check('scene import roundtrip',ev('exported().nodes.map(n=>n.id)')==[n['id'] for n in original['nodes']])
            disconnected=json.loads(json.dumps(original))
            for p in disconnected['portals']:p['enabled']=False
            load(disconnected);check('no fake paths when elevators disabled',ev('!!preview.error && preview.legs.length===0 && meta===null'))
            load({**original,'nodes':original['nodes'][:2]});check('two endpoints can preview without GA',ev('preview.legs.length===1') and page.locator('#planBtn').is_disabled())
            load({**original,'nodes':[]});check('empty scene supports map editing',ev('scene.nodes.length===0 && floors.length===2 && preview.legs.length===0'))
            load(original)
            page.set_viewport_size(dict(width=390,height=844));snapshot('editor-mobile')
            check('mobile has no horizontal overflow',ev('document.documentElement.scrollWidth<=innerWidth+2'))
            check('no JavaScript errors',not errors)
            if not args.offline_harness:
                check('native HTTP loaded editor and preview',any('/editor.js' in p for p in requests) and any('/api/editor/preview' in p for p in requests))
            report=dict(mode='DOM-to-HTTP harness' if args.offline_harness else 'native HTTP / unchanged CSP',passed=len(checks),checks=checks,errors=errors)
            (out/'editor-browser-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
            print(json.dumps(report,ensure_ascii=False,indent=2))
            browser.close()
    finally:server.shutdown();server.server_close()

if __name__=='__main__':run()
