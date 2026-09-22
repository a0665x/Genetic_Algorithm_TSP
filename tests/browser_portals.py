"""Paired elevator and bilingual UI acceptance tests (native HTTP by default).

--offline-harness uses an isolated DOM connected to a real loopback API; it does
not change browser policy and does not verify native browser networking or CSP.
"""
import argparse
import copy
import json
from pathlib import Path
import re
import sys
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import Handler

def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline-harness',action='store_true')
    parser.add_argument('--chromium',default=None)
    args=parser.parse_args()
    out=ROOT/'test-artifacts';out.mkdir(exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_address[1]}'
    checks=[];errors=[];calls=[]
    def http(path,data=None,language='en'):
        if not isinstance(path,str) or not path.startswith('/api/'):raise ValueError('Local API only')
        calls.append(path)
        req=Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json','Accept-Language':language})
        try:
            with urlopen(req,timeout=60) as r:return dict(ok=True,status=r.status,value=json.load(r))
        except HTTPError as e:return dict(ok=False,status=e.code,value=json.load(e))
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=args.chromium)
            page=browser.new_page(viewport=dict(width=1440,height=1120),device_scale_factor=1)
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:calls.append(r.url.removeprefix(base)))
            page.on('dialog',lambda d:d.accept())
            if args.offline_harness:
                page.expose_function('harnessHttp',http)
                page.set_content(re.sub(r'<link[^>]+>|<script[^>]+></script>','',(ROOT/'web/editor.html').read_text()))
                for asset in ['studio.css','editor.css']:page.add_style_tag(content=(ROOT/'web'/asset).read_text())
                page.evaluate("""() => {window.fetch=async(path,opts={})=>{const r=await window.harnessHttp(path,opts.body?JSON.parse(opts.body):null,opts.headers?.['Accept-Language']||'en');return {ok:r.ok,status:r.status,json:async()=>r.value};};}""")
                page.evaluate('(d)=>{window.DISPATCH_MESSAGES=d;}',json.loads((ROOT/'web/locales.json').read_text()))
                for asset in ['i18n.js','editor.js','portal-editor.js']:page.add_script_tag(content=(ROOT/'web'/asset).read_text())
            else:page.goto(base)
            def ev(expr):return page.evaluate('() => '+expr)
            def wait(expr):page.wait_for_function('() => '+expr,timeout=40000)
            def ready():wait('preview && !previewRunning && !previewQueued')
            def check(name,value):
                assert value,name
                checks.append(name);print('PASS:',name,flush=True)
            def shot(name):page.screenshot(path=str(out/(name+'.png')),full_page=True)
            def position(fid,x,y):
                q=page.evaluate('(p)=>project(p)',dict(floor=fid,x=x+.5,y=y+.5));box=page.locator('#mapCanvas').bounding_box()
                return box['x']+q['x'],box['y']+q['y']
            def place(pid,side,x,y):
                card=page.locator(f'.portal-setting[data-portal="{pid}"] .endpoint-card[data-side="{side}"]')
                card.locator('.placeEndpoint').click()
                wait('portalPick!==null && !document.getElementById("settingsDialog").open');ready()
                fid=ev('portalPick.floor');page.mouse.click(*position(fid,x,y));ready()
            def settings():page.click('#settingsBtn');wait('draftPreflight!==null')
            def save():page.click('#applySettingsBtn');wait('!document.getElementById("settingsDialog").open');ready()
            def load(s):
                before=ev('revision');page.set_input_files('#importFile',dict(name='scene.json',mimeType='application/json',buffer=json.dumps(s).encode()))
                wait(f'revision>{before}');ready()
            ready();original=ev('exported()')
            check('English is the initial language',ev('I18n.language==="en" && document.documentElement.lang==="en"') and 'Run GA' in page.locator('#planBtn').inner_text())
            before=ev('JSON.stringify(exported())')
            page.select_option('#languageSelect','zh-Hant')
            check('Chinese labels, right-click text and tooltips', 'GA 排程' in page.locator('#planBtn').inner_text() and page.locator('#contextAdd').inner_text()=='＋ 在此新增節點' and '總可等待' in page.locator('label[title]').first.get_attribute('title'))
            check('language change does not edit the scene',ev('JSON.stringify(exported())')==before)
            page.select_option('#languageSelect','en');shot('portals-english')
            settings();page.click('#addPortalBtn');wait('draft.portals.some(p=>p.id==="Ea")')
            check('new elevator has two explicit null coordinates',ev('draft.portals.find(p=>p.id==="Ea").a.x===null && draft.portals.find(p=>p.id==="Ea").b.y===null'))
            save();check('incomplete draft blocks GA without a job',page.locator('#planBtn').is_disabled() and ev('preview.legs.length===0 && preview.preflight.ok===false') and '/api/editor/jobs' not in calls)
            settings();place('Ea','a',20,80)
            check('first endpoint is placed but pairing stays incomplete',ev('scene.portals.find(p=>p.id==="Ea").a.x===20 && scene.portals.find(p=>p.id==="Ea").b.x===null') and page.locator('#planBtn').is_disabled())
            page.click('#structureBtn')
            check('stacked view draws a half link and no invented destination',ev('portalRenderState.some(p=>p.id==="Ea" && p.kind==="half" && p.missing==="b") && scene.portals.find(p=>p.id==="Ea").b.x===null'))
            check('missing endpoint diagnostics name the exact pair', 'Ea_F2' in page.locator('#preflightIssues').inner_text())
            shot('portals-half-english')
            page.select_option('#languageSelect','zh-Hant')
            check('existing preflight error switches to Chinese', '尚未' in page.locator('#preflightIssues').inner_text() or '未放置' in page.locator('#preflightIssues').inner_text())
            shot('portals-half-chinese');page.select_option('#languageSelect','en')
            settings();page.select_option('#dialogLanguageSelect','zh-Hant')
            check('modal labels switch live',page.locator('.placeEndpoint').last.inner_text()=='在地圖上設定' or '地圖' in page.locator('.placeEndpoint').last.inner_text())
            check('draft values survive language switch',ev('draft.portals.find(p=>p.id==="Ea").a.x===20'))
            page.select_option('#dialogLanguageSelect','en');shot('portals-pair-editor')
            place('Ea','b',20,80)
            check('second endpoint restores routing',ev('preview.preflight.ok && preview.legs.length===7') and not page.locator('#planBtn').is_disabled())
            page.click('[data-floor="F2"]');a=position('F2',20,80);b=position('F2',25,80)
            page.mouse.move(*a);page.mouse.down();page.mouse.move(*b,steps=8);page.mouse.up();ready()
            check('elevator endpoints drag directly on the map',ev('scene.portals.find(p=>p.id==="Ea").b.x===25'))
            page.mouse.click(*position('F2',25,80),button='right');wait('document.getElementById("settingsDialog").open')
            check('right-click opens paired elevator editor',page.locator('.portal-setting[data-portal="Ea"]').is_visible())
            card=page.locator('.portal-setting[data-portal="Ea"]');card.locator('[data-side="b"] .clearEndpoint').click();card.locator('.portalEnabled').uncheck();save()
            check('disabled incomplete draft is warning-only and excluded',ev('preview.preflight.ok && preview.preflight.issues.every(i=>i.severity==="warning") && !preview.legs.some(l=>l.segments.some(s=>s.id==="Ea"))'))
            settings();page.locator('.portal-setting[data-portal="Ea"] .portalEnabled').check();save()
            check('reenabling incomplete link blocks again',page.locator('#planBtn').is_disabled())
            settings();side=page.locator('.portal-setting[data-portal="Ea"] [data-side="b"]');side.locator('details summary').click()
            side.locator('[data-axis="x"]').fill('0');side.locator('[data-axis="x"]').press('Tab');side.locator('[data-axis="y"]').fill('0');side.locator('[data-axis="y"]').press('Tab');save()
            check('wall endpoint is rejected before path calculation',ev('preview.preflight.issues.some(i=>i.code==="portal.blocked") && preview.legs.length===0'))
            settings();side=page.locator('.portal-setting[data-portal="Ea"] [data-side="b"]');side.locator('.endpointFloor').select_option('F1');save()
            check('same-floor pair is invalid and reassignment clears coordinates',ev('scene.portals.find(p=>p.id==="Ea").b.x===null && preview.preflight.issues.some(i=>i.code==="portal.same_floor")'))
            load(original);settings()
            # Real file uploads: two separate occupancy images, not mocked image metadata.
            from scheduler.building import demo_floor
            from io import BytesIO
            files=[]
            for k in (1,2):
                buf=BytesIO();demo_floor(k).save(buf,format='PNG');files.append(dict(name=f'Scan_{k}F.png',mimeType='image/png',buffer=buf.getvalue()))
            page.click('#addFloorBtn');page.set_input_files('#floorUpload',files)
            wait('draft.floors.length===4');wait('draftPreflight!==null')
            check('multiple uploaded maps become independent floors',ev('draft.floors[2].id==="1F" && draft.floors[3].id==="2F" && draft.floors[2].name==="Scan_1F"'))
            page.click('#addPortalBtn')
            page.locator('.portal-setting[data-portal="Ea"] [data-side="a"] .endpointFloor').select_option(label="Scan_1F")
            page.locator('.portal-setting[data-portal="Ea"] [data-side="b"] .endpointFloor').select_option(label="Scan_2F")
            place('Ea','a',20,80);settings();place('Ea','b',20,80)
            check('uploaded floor pair labels use Ea_1F and Ea_2F',ev('preview.preflight.portals.find(p=>p.id==="Ea").labels.a==="Ea_1F" && preview.preflight.portals.find(p=>p.id==="Ea").labels.b==="Ea_2F"'))
            page.click('#structureBtn');shot('portals-four-floors')
            settings();page.locator('.floor-setting[data-floor="2F"] .removeFloor').click();save()
            check('deleting a floor keeps a repairable dangling link',ev('scene.portals.some(p=>p.id==="Ea") && preview.preflight.issues.some(i=>i.code==="portal.floor_missing")'))
            load(original);settings();page.locator('.floor-setting[data-floor="F2"] .replaceFloor').click();page.set_input_files('#floorUpload',files[0]);wait('draft.portals.every(p=>p.b.x===null)');save()
            check('replacing map clears old portal coordinates',ev('scene.portals.every(p=>p.b.x===null) && preview.preflight.ok===false'))
            load(original);page.click('#planBtn');wait('result!==null && !busy')
            snapshot=ev('JSON.stringify({scene:exported(),meta,history,result})')
            page.click('#formulaDetails > summary')
            check('real W/D/T values and formulas after GA',page.locator('#matrixTable tbody tr').count()==8 and page.locator('.equation').count()==8)
            check('English formula explanation', 'order destinations' in page.locator('.equation').nth(2).inner_text())
            page.select_option('#languageSelect','zh-Hant')
            check('Chinese math, elite and chart descriptions', '目的' in page.locator('.equation').nth(2).inner_text() and '保留' in page.locator('#eliteChange').inner_text())
            check('language switch preserves exact matrices, history and model',ev('JSON.stringify({scene:exported(),meta,history,result})')==snapshot)
            shot('portals-math-chinese');page.select_option('#languageSelect','en')
            check('English has no untranslated Chinese application text',not re.search('[\u4e00-\u9fff]',page.locator('body').inner_text().replace('繁體中文','')))
            check('tooltips and accessibility labels translated',page.locator('#mapCanvas').get_attribute('aria-label').startswith('Route map.') and 'Move' in page.locator('.grip').first.get_attribute('aria-label'))
            page.locator('.route-item').nth(1).click();page.fill('#nodeName','');page.locator('#nodeName').press('Tab')
            page.locator('#nodeName').evaluate('(e)=>e.reportValidity()')
            check('validation bubble uses current language',page.locator('#nodeName').evaluate('(e)=>e.validationMessage')=='Use a non-empty, unique name.' or 'required' in page.locator('#nodeName').evaluate('(e)=>e.validationMessage'))
            page.select_option('#languageSelect','zh-Hant')
            check('existing validation message switches language',bool(re.search('[\u4e00-\u9fff]',page.locator('#nodeName').evaluate('(e)=>e.validationMessage'))))
            page.fill('#nodeName','A');page.locator('#nodeName').press('Tab');ready();page.select_option('#languageSelect','en')
            page.set_viewport_size(dict(width=390,height=844));shot('portals-mobile')
            check('mobile has no horizontal overflow',ev('document.documentElement.scrollWidth<=innerWidth+2'))
            check('no missing translation keys',ev('I18n.missing.size===0'))
            check('no JavaScript errors',not errors)
            report={'mode':'isolated DOM-to-HTTP harness' if args.offline_harness else 'native HTTP','passed':len(checks),'checks':checks,'errors':errors}
            (out/'portal-browser-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
            browser.close()
    finally:server.shutdown();server.server_close()
if __name__=='__main__':run()
