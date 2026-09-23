#!/usr/bin/env python3
"""Run the local UI: python app.py --port 8000 (loopback by default)."""
import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
from scheduler.api import ROOT,MAPS,Jobs,image_from_request
from io import BytesIO
import base64

from scheduler.building import BuildingJobs, demo_scene, validate_scene

from scheduler.editor import EditorJobs, editor_demo, preview_editor, preflight_editor

from scheduler.messages import localize_payload, exception_payload
from scheduler.map_import import review_map, reference_maps, reference_map

editor_jobs=EditorJobs()
jobs=Jobs()
building_jobs=BuildingJobs()

class Handler(BaseHTTPRequestHandler):
    def send_bytes(self,body,status=200,kind='application/json'):
        self.send_response(status);self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def json(self,data,status=200):
        if self.path.startswith(('/api/editor/', '/api/map-preview')):
            data = localize_payload(data, self.headers.get('Accept-Language', 'en'))
        self.send_bytes(json.dumps(data,ensure_ascii=False,allow_nan=False).encode(),status)
    def do_GET(self):
        u=urlparse(self.path);p=u.path
        try:
            if p=='/api/editor/reference-maps':
                return self.json(reference_maps())
            if p.startswith('/api/editor/reference-maps/'):
                return self.json(reference_map(p.split('/')[-1]))
            if p=='/messages.js':
                return self.send_bytes(b'window.DISPATCH_MESSAGES = '+(ROOT/'web/locales.json').read_bytes()+b';',kind='application/javascript')
            if p=='/api/editor/demo':
                return self.json(editor_demo())
            if p.startswith('/api/editor/jobs/'):
                after=int(parse_qs(u.query).get('after',['0'])[0])
                if after<0: raise ValueError('after 必須大於等於 0')
                return self.json(editor_jobs.get(p.split('/')[-1],after))
            if p=='/api/studio/demo':
                return self.json(demo_scene())
            if p.startswith('/api/studio/jobs/'):
                after=int(parse_qs(u.query).get('after',['0'])[0])
                if after<0: raise ValueError('after 必須大於等於 0')
                return self.json(building_jobs.get(p.split('/')[-1],after))
            if p=='/api/maps':
                return self.json([dict(id=id,name=name,**json.loads((ROOT/'data/map'/f'{id}.json').read_text())) for id,name in MAPS.items()])
            if p.startswith('/api/jobs/'):
                after=int(parse_qs(u.query).get('after',['0'])[0])
                if after<0:raise ValueError('after 必須大於等於 0')
                return self.json(jobs.get(p.split('/')[-1],after))
            allowed={'/map-import.js':ROOT/'web/map-import.js','/map-import.css':ROOT/'web/map-import.css','/':ROOT/'web/editor.html','/studio':ROOT/'web/studio.html','/i18n.js':ROOT/'web/i18n.js','/portal-editor.js':ROOT/'web/portal-editor.js','/editor.js':ROOT/'web/editor.js','/editor.css':ROOT/'web/editor.css','/legacy':ROOT/'web/index.html','/studio.js':ROOT/'web/studio.js','/studio.css':ROOT/'web/studio.css','/app.js':ROOT/'web/app.js','/style.css':ROOT/'web/style.css'}
            allowed.update({f'/data/map/{m}.png':ROOT/'data/map'/f'{m}.png' for m in MAPS})
            file=allowed.get(p)
            if file is None:return self.json({'error':'Not found'},404)
            return self.send_bytes(file.read_bytes(),kind=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
        except KeyError:return self.json({'error':'規劃不存在或已過期，請重新執行。'},404)
        except ValueError as e:return self.json(exception_payload(e),400)
    def do_POST(self):
        # Local application: reject cross-origin browser writes and require JSON.
        origin=self.headers.get('Origin')
        if origin and origin!=f'http://{self.headers.get("Host")}':return self.json({'error':'Origin rejected'},403)
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.json({'error':'JSON required'},415)
        try:
            size=int(self.headers.get('Content-Length','0'))
            limit=12_000_000 if self.path.startswith(('/api/studio/','/api/editor/')) else 3_000_000
            if not 0<size<=limit:raise ValueError(f'請求大小需小於 {limit//1_000_000} MB。')
            data=json.loads(self.rfile.read(size))
            if self.path=='/api/editor/map-review':
                return self.json(review_map(data))
            if self.path=='/api/editor/preflight':
                return self.json(preflight_editor(data))
            if self.path=='/api/editor/preview':
                return self.json(preview_editor(data))
            if self.path=='/api/editor/jobs':
                return self.json({'id':editor_jobs.start(data)},202)
            if self.path.startswith('/api/editor/jobs/') and self.path.endswith('/cancel'):
                editor_jobs.cancel(self.path.split('/')[-2]);return self.json({'ok':True})
            if self.path=='/api/studio/jobs':
                return self.json({'id':building_jobs.start(data)},202)
            if self.path=='/api/studio/preview':
                v=validate_scene(data,require_orders=False,check_clearance=False)
                return self.json({'floors':v['views'],'portals':v['portals']})
            if self.path.startswith('/api/studio/jobs/') and self.path.endswith('/cancel'):
                building_jobs.cancel(self.path.split('/')[-2]);return self.json({'ok':True})
            if self.path=='/api/jobs':return self.json({'id':jobs.start(data)},202)
            if self.path=='/api/map-preview':
                im=image_from_request(data);buf=BytesIO();im.save(buf,format='PNG')
                return self.json({'data':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode(),'width':im.width,'height':im.height})
            if self.path.startswith('/api/jobs/') and self.path.endswith('/cancel'):
                jobs.cancel(self.path.split('/')[-2]);return self.json({'ok':True})
            return self.json({'error':'Not found'},404)
        except KeyError:return self.json({'error':'規劃不存在。'},404)
        except (ValueError,TypeError) as e:return self.json(exception_payload(e),400)
    def log_message(self,format,*args):
        if '/api/jobs/' not in str(args):super().log_message(format,*args)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    print(f'Robot Dispatch Lab → http://{args.host}:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
