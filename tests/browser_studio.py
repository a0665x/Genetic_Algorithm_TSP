"""Chromium UI integration checks, with optional offline DOM-to-HTTP harness.

Normal: python tests/browser_studio.py
Restricted hosts: --offline-harness --chromium /usr/bin/chromium
The harness does NOT override browser policies. It loads local HTML/CSS/JS into
about:blank and replaces fetch with a Python binding to the real loopback API.
It verifies DOM/Canvas and backend interactions, not browser networking or CSP.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import Handler
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline-harness',action='store_true')
    parser.add_argument('--chromium',default=None)
    args=parser.parse_args()
    artifacts=ROOT/'test-artifacts';artifacts.mkdir(exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_address[1]}'
    checks=[]; errors=[]
    def check(name,condition):
        assert condition,name
        checks.append(name)
    def http(path,data=None):
        # Only the test server's own /api/ endpoints; no arbitrary URL forwarding.
        if not isinstance(path,str) or not path.startswith('/api/'):
            raise ValueError('Only local test API paths are supported')
        req=Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
        try:
            with urlopen(req,timeout=30) as r:return dict(ok=True,status=r.status,value=json.load(r))
        except HTTPError as e:return dict(ok=False,status=e.code,value=json.load(e))
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,executable_path=args.chromium)
            page=browser.new_page(viewport=dict(width=1440,height=1200),device_scale_factor=1)
            page.on('pageerror',lambda e:errors.append(str(e)))
            if args.offline_harness:
                page.expose_function('harnessHttp',http)
                html=(ROOT/'web/studio.html').read_text()
                html=re.sub(r'<link[^>]+>|<script[^>]+></script>','',html)
                page.set_content(html)
                page.add_style_tag(content=(ROOT/'web/studio.css').read_text())
                page.evaluate('''() => { window.fetch=async(path,opts={})=>{
                    const r=await window.harnessHttp(path,opts.body?JSON.parse(opts.body):null);
                    return {ok:r.ok,status:r.status,json:async()=>r.value};}; }''')
                page.add_script_tag(content=(ROOT/'web/studio.js').read_text())
            else:
                page.goto(base)
            page.wait_for_function('document.querySelectorAll(".order-item").length===6')
            original=page.evaluate('JSON.parse(JSON.stringify(scene))')
            check('six orders; advanced controls hidden by default',page.locator('.order-item').count()==6 and not page.locator('#orderAdvanced').get_attribute('open') and not page.locator('#mathDialog').is_visible())
            page.click('#planBtn')
            page.wait_for_function('document.getElementById("status").textContent.includes("規劃完成")',timeout=60000)
            check('real run and 41 replay generations',page.evaluate('history.length===41 && !!meta && !!result'))
            check('UI uses backend loss',page.evaluate('Math.abs(Number(document.getElementById("loss").textContent)-result.best.loss)<0.01'))
            page.screenshot(path=str(artifacts/'studio-plan.png'),full_page=True)
            page.click('#structureBtn')
            check('both floor transforms rendered',page.evaluate('Object.keys(transforms).length===2'))
            page.screenshot(path=str(artifacts/'studio-building.png'),full_page=True)
            page.click('#mathBtn');page.click('[data-matrix="time_matrix"]')
            check('7x7 real time matrix',page.locator('#matrixTable tbody tr').count()==7)
            page.click('[data-edge="0:4"]')
            check('selected cross-floor cell explains an elevator', '等待' in page.locator('#edgeDetail').inner_text())
            page.click('#formulaDetails > summary')
            check('formula and per-feature substitution available',page.locator('.equation').count()==8 and page.locator('#weightDetails tbody tr').count()==6)
            page.screenshot(path=str(artifacts/'studio-math.png'),full_page=True)
            page.click('#showEdgeBtn');check('cell shows a real cross-floor path',page.evaluate('selectedEdge==="0:4" && structure'))
            page.click('[data-floor="F1"]')
            page.click('#addBtn')
            def click_at(floor,x,y):
                q=page.evaluate('(p)=>project(p)',dict(floor=floor,x=x+.5,y=y+.5))
                box=page.locator('#mapCanvas').bounding_box();page.mouse.click(box['x']+q['x'],box['y']+q['y'])
            click_at('F1',96,80)
            check('new order clears stale calculations',page.locator('.order-item').count()==7 and page.locator('#loss').inner_text()=='—' and page.locator('#mathBtn').is_disabled())
            page.click('[data-floor="F2"]');page.click('#moveBtn');click_at('F2',96,80)
            check('order moves across floors',page.evaluate('scene.orders[selected].floor==="F2" && scene.orders[selected].x===96'))
            page.click('#deleteBtn');check('delete restores six orders',page.locator('.order-item').count()==6)
            page.locator('.order-item').first.click()
            page.fill('#orderName','<img src=x onerror=alert(1)>');page.locator('#orderName').press('Tab')
            check('order labels are escaped',page.locator('#orderList img').count()==0 and '<img' in page.locator('.order-label strong').first.inner_text())
            page.fill('#orderName','A');page.locator('#orderName').press('Tab')
            page.fill('#waited','5');page.locator('#waited').press('Tab');page.fill('#patience','2');page.locator('#patience').press('Tab')
            check('minutes convert exactly to backend seconds',page.evaluate('scene.orders[0].waited===300 && scene.orders[0].patience===120'))
            page.click('#settingsBtn');page.locator('#settingsDialog > details').nth(1).locator('summary').click()
            page.locator('#coefficientSettings input').nth(1).fill('0');page.locator('#coefficientSettings input').nth(1).press('Tab')
            page.click('#applySettingsBtn');page.wait_for_function('!document.getElementById("settingsDialog").open')
            page.click('#planBtn');page.wait_for_function('document.getElementById("status").textContent.includes("規劃完成")',timeout=60000)
            check('coefficient zero reaches real score calculation',page.evaluate('meta.coefficients.wait===0 && meta.weights.every(w=>w.contributions.wait===0)'))
            page.locator('#generation').evaluate('(e)=>{e.value=0;e.dispatchEvent(new Event("input"));}')
            check('replay uses first generation', '第 0 代' in page.locator('#generationLabel').inner_text())
            page.set_input_files('#importFile',dict(name='scene.json',mimeType='application/json',buffer=json.dumps(original).encode()))
            page.wait_for_function('document.getElementById("status").textContent.includes("已匯入")')
            check('scene import roundtrip clears stale run',page.evaluate('scene.orders[0].waited===0 && meta===null'))
            page.click('#settingsBtn')
            for checkbox in page.locator('.portalEnabled').all():checkbox.uncheck()
            page.click('#applySettingsBtn');page.wait_for_function('!document.getElementById("settingsDialog").open')
            page.click('#planBtn');page.wait_for_function('document.getElementById("status").textContent.includes("不可達")',timeout=30000)
            check('disabled elevators fail without fake paths',page.evaluate('meta===null && history.length===0'))
            page.set_viewport_size(dict(width=390,height=844));page.screenshot(path=str(artifacts/'studio-mobile.png'),full_page=True)
            check('mobile viewport has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth <= innerWidth+2'))
            check('no JavaScript errors',not errors)
            report=dict(mode='offline DOM-to-HTTP harness' if args.offline_harness else 'real browser HTTP',
                        passed=len(checks),checks=checks,errors=errors,
                        asset_sha256={n:hashlib.sha256((ROOT/'web'/n).read_bytes()).hexdigest() for n in ('studio.html','studio.js','studio.css')})
            (artifacts/'browser-report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
            print(json.dumps(report,indent=2,ensure_ascii=False));browser.close()
    finally:server.shutdown();server.server_close()

if __name__=='__main__':main()
