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

jobs=Jobs()

class Handler(BaseHTTPRequestHandler):
    def send_bytes(self,body,status=200,kind='application/json'):
        self.send_response(status);self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def json(self,data,status=200):self.send_bytes(json.dumps(data,ensure_ascii=False,allow_nan=False).encode(),status)
    def do_GET(self):
        u=urlparse(self.path);p=u.path
        try:
            if p=='/api/maps':
                return self.json([dict(id=id,name=name,**json.loads((ROOT/'data/map'/f'{id}.json').read_text())) for id,name in MAPS.items()])
            if p.startswith('/api/jobs/'):
                after=int(parse_qs(u.query).get('after',['0'])[0])
                if after<0:raise ValueError('after 必須大於等於 0')
                return self.json(jobs.get(p.split('/')[-1],after))
            allowed={'/':ROOT/'web/index.html','/app.js':ROOT/'web/app.js','/style.css':ROOT/'web/style.css'}
            allowed.update({f'/data/map/{m}.png':ROOT/'data/map'/f'{m}.png' for m in MAPS})
            file=allowed.get(p)
            if file is None:return self.json({'error':'Not found'},404)
            return self.send_bytes(file.read_bytes(),kind=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
        except KeyError:return self.json({'error':'規劃不存在或已過期，請重新執行。'},404)
        except ValueError as e:return self.json({'error':str(e)},400)
    def do_POST(self):
        # Local application: reject cross-origin browser writes and require JSON.
        origin=self.headers.get('Origin')
        if origin and origin!=f'http://{self.headers.get("Host")}':return self.json({'error':'Origin rejected'},403)
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.json({'error':'JSON required'},415)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=3_000_000:raise ValueError('請求大小需小於 3 MB。')
            data=json.loads(self.rfile.read(size))
            if self.path=='/api/jobs':return self.json({'id':jobs.start(data)},202)
            if self.path=='/api/map-preview':
                im=image_from_request(data);buf=BytesIO();im.save(buf,format='PNG')
                return self.json({'data':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode(),'width':im.width,'height':im.height})
            if self.path.startswith('/api/jobs/') and self.path.endswith('/cancel'):
                jobs.cancel(self.path.split('/')[-2]);return self.json({'ok':True})
            return self.json({'error':'Not found'},404)
        except KeyError:return self.json({'error':'規劃不存在。'},404)
        except (ValueError,TypeError) as e:return self.json({'error':str(e)},400)
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
