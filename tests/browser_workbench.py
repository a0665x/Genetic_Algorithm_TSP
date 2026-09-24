"""Native Sheet workbench acceptance checks.

Use --offline-harness only on managed hosts that disallow native navigation.
That mode loads exact DOM/CSS/JS and bridges to the real local HTTP server; it
makes no native networking/CSP claim and never changes browser policy.
"""
import argparse
from io import BytesIO
import json
from pathlib import Path
import re
import sys
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import Handler


def run():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--offline-harness',action='store_true');ap.add_argument('--chromium')
    args=ap.parse_args()
    out=ROOT/'test-artifacts';out.mkdir(exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_address[1]}'
    checks=[];errors=[];calls=[]
    def http(path,data=None,language='en'):
        assert path.startswith('/api/');calls.append((path,'POST' if data is not None else 'GET'))
        request=Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json','Accept-Language':language})
        try:
            with urlopen(request,timeout=60) as r:return dict(ok=True,status=r.status,value=json.load(r))
        except HTTPError as e:return dict(ok=False,status=e.code,value=json.load(e))
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=args.chromium)
            page=browser.new_page(viewport=dict(width=1440,height=1060),device_scale_factor=1)
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('dialog',lambda d:d.accept())
            if args.offline_harness:
                page.expose_function('harnessHttp',http)
                page.set_content(re.sub(r'<script\b[^>]*>[\s\S]*?</script>|<link\b[^>]*>','',(ROOT/'web/editor.html').read_text()))
                for asset in ['studio.css','editor.css','map-import.css','sheet-workbench.css']:
                    page.add_style_tag(content=(ROOT/'web'/asset).read_text())
                page.evaluate("""() => { window.fetch=async(path,opts={})=>{const r=await window.harnessHttp(path,opts.body?JSON.parse(opts.body):null,opts.headers?.['Accept-Language']||'en');return {ok:r.ok,status:r.status,json:async()=>r.value};}; }""")
                page.evaluate('(v)=>window.DISPATCH_MESSAGES=v',json.loads((ROOT/'web/locales.json').read_text()))
                for asset in ['i18n.js','editor.js','portal-editor.js','map-import.js','sheet-workbench.js']:
                    page.add_script_tag(content=(ROOT/'web'/asset).read_text())
            else:
                page.on('request',lambda r:calls.append((r.url.removeprefix(base),r.method)))
                page.goto(base)
            page.set_default_timeout(15000)
            def ev(s):return page.evaluate('()=>('+s+')')
            def wait(s):page.wait_for_function('()=>('+s+')',timeout=60000)
            def ready():wait('!!preview && !previewRunning && !previewQueued && !uploadInProgress && !mapApplying')
            def check(name,condition):
                assert condition,name
                checks.append(name);print('PASS',name,flush=True)
            def at(fid,x,y,head=False):
                q=page.evaluate('(v)=>project(v)',dict(floor=fid,x=x+.5,y=y+.5))
                box=page.locator('#mapCanvas').bounding_box()
                return box['x']+q['x'],box['y']+q['y']-(20 if head else 0)
            def drag(a,b):
                page.mouse.move(*a);page.mouse.down();page.mouse.move(*b,steps=14);page.mouse.up()
            def screenshot(name):page.screenshot(path=str(out/(name+'.png')),full_page=True)
            ready()
            check('first visit has exactly one sheet and no preconfigured tasks or elevators',ev('scene.floors.length===1 && scene.nodes.length===0 && scene.portals.length===0'))
            check('floor setup is deferred and observatory is retained but collapsed',not page.locator('#settingsDialog').is_visible() and not page.locator('#observatoryDetails').get_attribute('open'))
            check('new channel tool is beside the node tool',page.locator('.tool-pair #addElevatorBtn').count()==1)
            screenshot('sheet-first')
            page.click('#addBtn')
            check('armed node button and tool banner are visible',page.locator('#addBtn').get_attribute('aria-pressed')=='true' and page.locator('#toolState').is_visible())
            for x,y in [(40,80),(100,60),(180,110)]:page.mouse.click(*at('sheet-1',x,y));ready()
            check('node clicks immediately produce ordered A* before GA',ev('scene.nodes.length===3 && preview.legs.length===2 && history.length===0'))
            page.keyboard.press('Escape')
            check('Escape clears pressed tool state',page.locator('#addBtn').get_attribute('aria-pressed')=='false')
            page.click('#addElevatorBtn')
            check('one-sheet elevator action opens a clear next step',page.locator('#needSheetDialog').is_visible())
            page.click('#blankSecondSheet');ready()
            check('second sheet is added without floor or coefficient forms',ev('scene.floors.length===2') and not page.locator('#settingsDialog').is_visible())
            page.click('[data-floor="sheet-1"]');page.click('#addElevatorBtn')
            check('elevator placement is armed with step-one feedback',ev('portalPick.side==="a"') and page.locator('#addElevatorBtn').get_attribute('aria-pressed')=='true')
            page.mouse.click(*at('sheet-1',110,90));ready()
            check('first click advances to the other sheet, not a route node',ev('portalPick.side==="b" && floorId==="sheet-2" && scene.nodes.length===3'))
            page.mouse.click(*at('sheet-2',130,90));ready()
            check('two clicks create one explicit channel with zero added route nodes',ev('scene.portals.length===1 && scene.portals[0].a.floor==="sheet-1" && scene.portals[0].b.floor==="sheet-2" && scene.nodes.length===3 && preview.preflight.ok'))
            drag(at('sheet-2',130,90),at('sheet-2',140,95));ready()
            check('top-down channel drag updates the paired endpoint',ev('scene.portals[0].b.x===140 && scene.portals[0].b.y===95'))
            drag(at('sheet-2',140,95),at('sheet-2',0,0))
            check('wall drop is rejected without modifying endpoint',ev('scene.portals[0].b.x===140 && scene.portals[0].b.y===95'))
            # A real upload, not a scene-state shortcut. The basic import has one confirmation button.
            im=Image.new('RGB',(120,120),'white');ImageDraw.Draw(im).rectangle((0,0,119,119),outline='black',width=3)
            buf=BytesIO();im.save(buf,format='PNG')
            page.set_input_files('#floorUpload',dict(name='Third-map.png',mimeType='image/png',buffer=buf.getvalue()))
            wait('!!mapReview && !mapReading')
            check('automatic import shows preview without floor or threshold questions',page.locator('#mapImportDialog').is_visible() and not page.locator('#mapFloorId').is_visible() and not page.locator('#mapWall').is_visible())
            check('Use map confirms review without a redundant checkbox',page.locator('#applyMapImport').is_enabled() and not page.locator('#mapReviewed').is_visible())
            screenshot('sheet-import')
            page.locator('#applyMapImport').evaluate('(e)=>{e.click();e.click();}');ready()
            check('repeated confirmation commits one sheet with retained source data',ev('scene.floors.length===3 && !!scene.floors[2].semantics.source_data') and not page.locator('#mapImportDialog').is_visible())
            third=ev('scene.floors[2].id')
            page.click('#structureBtn')
            check('building view is visibly active and renders all sheets',page.locator('#structureBtn').get_attribute('aria-pressed')=='true' and ev('Object.keys(transforms).length===3'))
            a=at('sheet-1',110,90);b=at('sheet-2',140,95)
            grip=(a[0]+.78*(b[0]-a[0]),a[1]+.78*(b[1]-a[1]))
            target=at(third,75,75)
            page.mouse.move(*grip);page.mouse.down();page.mouse.move(*target,steps=14)
            check('dragging a line handle shows live target sheet and endpoint readout',ev('gesture?.type==="channel-drag" && gesture.point?.floor===scene.floors[2].id') and 'Third-map' in page.locator('#channelDock').inner_text())
            screenshot('sheet-dragging')
            page.mouse.up();ready()
            check('line-handle drop rebinds only the chosen endpoint and keeps nodes untouched',ev(f'scene.portals[0].b.floor==={json.dumps(third)} && scene.portals[0].b.x===75 && scene.nodes.length===3'))
            screenshot('sheet-channels')
            # Rejected same-sheet placement rolls back, rather than inventing a portal edge.
            drag(at(third,75,75),at('sheet-1',90,130))
            check('same-sheet portal drop is rejected',ev(f'scene.portals[0].b.floor==={json.dumps(third)}'))
            page.click(f'[data-floor="{third}"]');page.click('#addBtn');page.mouse.click(*at(third,80,90));ready();page.keyboard.press('Escape')
            check('cross-sheet ordered preview traverses the explicitly rebound elevator',ev('preview.legs.at(-1).segments.some(s=>s.kind==="elevator")'))
            # Cancelled pointer gestures cannot leak to the persistent scene.
            original=ev('JSON.stringify(scene.portals)')
            page.mouse.move(*at(third,75,75));page.mouse.down();page.mouse.move(*at(third,70,90),steps=5)
            page.locator('#mapCanvas').dispatch_event('pointercancel');page.mouse.up()
            check('cancelled drag restores channel data',ev('JSON.stringify(scene.portals)')==original)
            page.click('#planBtn');wait('!!result && !busy')
            check('GA scheduling opens the retained evolution observatory',page.locator('#observatoryDetails').get_attribute('open') is not None and ev('history.length===41'))
            check('actual weight matrices and elite histories are retained',ev('!!meta.weight_matrix && history.every(h=>h.worlds.every(w=>!!w.elites))'))
            before=ev('JSON.stringify({result,history,weights:meta.weight_matrix,times:meta.time_matrix})')
            ga_count=sum(1 for path,method in calls if path=='/api/editor/jobs' and method=='POST')
            # Native HTML drag-and-drop of sheet handles (presentation-only).
            grip=page.locator('.sheet-tile').nth(2).locator('.sheet-grip')
            target=page.locator('.sheet-tile').first
            grip.drag_to(target,target_position=dict(x=3,y=15))
            check('sheet drag changes the persisted bottom-to-top order',ev(f'scene.floors[0].id==={json.dumps(third)}'))
            check('sheet sorting preserves all GA results and matrices',ev('JSON.stringify({result,history,weights:meta.weight_matrix,times:meta.time_matrix})')==before)
            check('sheet sorting starts no extra GA job',sum(1 for path,method in calls if path=='/api/editor/jobs' and method=='POST')==ga_count)
            page.click('#structureBtn')
            check('stack transforms follow current sheet order immediately',ev(f'transforms[{json.dumps(third)}].f > transforms["sheet-1"].f'))
            page.locator('.sheet-tile').first.click(button='right');page.click('#sheetMenuRename')
            page.fill('#sheetName','3F · Lab');page.locator('#sheetForm button[type=submit]').click()
            check('floor naming is optional, deferred and identity-safe',ev(f'scene.floors[0].name==="3F · Lab" && scene.portals[0].b.floor==={json.dumps(third)}'))
            page.click('#undoBtn')
            check('undo of a display-only change preserves GA results',ev('!!result && scene.floors[0].name==="Third-map"'))
            screenshot('sheet-evolution')
            page.locator('.observatory').evaluate('(e)=>e.scrollIntoView({block:"start"})')
            page.wait_for_timeout(500)
            page.screenshot(path=str(out/'sheet-evolution-focus.png'))
            page.evaluate('()=>window.scrollTo(0,0)')
            unchanged=ev('JSON.stringify(exported())')
            page.select_option('#languageSelect','zh-Hant')
            check('new tools and feedback switch to Traditional Chinese',page.locator('#addElevatorBtn').inner_text()=='＋ 電梯' and page.locator('#workbenchState').inner_text()=='已完成')
            check('language switch keeps scene and results unchanged',ev('JSON.stringify(exported())')==unchanged and ev('!!result'))
            page.select_option('#languageSelect','en')
            check('all used UI translation keys exist',ev('I18n.missing.size===0'))
            saved=ev('exported()')
            page.click('#addElevatorBtn')
            check('new channel is a repairable draft, never an added stop',ev('!!portalPick && scene.nodes.length===4'))
            page.set_input_files('#importFile',dict(name='saved.json',mimeType='application/json',buffer=json.dumps(saved).encode()))
            ready()
            check('scene import cancels obsolete placement and restores synchronized state',ev('!portalPick && mode==="select" && scene.portals.length===1 && preview.preflight.ok'))
            page.set_viewport_size(dict(width=390,height=844));screenshot('sheet-mobile')
            check('mobile has no horizontal overflow',ev('document.documentElement.scrollWidth<=innerWidth+2'))
            check('no JavaScript errors',not errors)
            report=dict(mode='isolated DOM + real HTTP' if args.offline_harness else 'native Chromium HTTP',passed=len(checks),checks=checks,errors=errors)
            (out/'workbench-report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
            print(json.dumps(report,indent=2,ensure_ascii=False));browser.close()
    finally:server.shutdown();server.server_close()

if __name__=='__main__':run()
