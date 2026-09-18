import unittest
import threading
import time
import json
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from app import Handler

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.url=f'http://127.0.0.1:{cls.server.server_address[1]}'
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def request(self,path,data=None,**headers):
        request=Request(self.url+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json',**headers})
        try:
            with urlopen(request,timeout=10) as r:return r.status,r.read()
        except HTTPError as e:return e.code,e.read()
    def test_end_to_end(self):
        code,body=self.request('/');self.assertEqual(code,200);self.assertIn(b'mapCanvas',body)
        self.assertEqual(self.request('/api/maps')[0],200)
        data={'map':'hotel','start':[15,80],'orders':[{'id':'A','x':28,'y':28},{'id':'B','x':208,'y':130}], 'settings':{'generations':10,'population':20,'worlds':3,'interval':2}}
        status,body=self.request('/api/jobs',data);self.assertEqual(status,202,body)
        id=json.loads(body)['id'];seen=0;history=[];meta=None
        for _ in range(100):
            status,body=self.request(f'/api/jobs/{id}?after={seen}');v=json.loads(body)
            if 'meta' in v:meta=v['meta']
            history+=v['history'];seen=v['count']
            if v['status'] in ('done','error'):break
            time.sleep(.01)
        self.assertEqual(v['status'],'done',v)
        self.assertEqual(len(history),11);self.assertEqual(len(v['result']['events']),5)
        self.assertEqual(sorted(v['result']['best']['route'][1:-1]),[1,2])
        self.assertEqual(len(meta['weight_matrix']),3);self.assertIn('0:1',meta['paths'])
        self.assertEqual(self.request('/api/jobs',dict(data,start=[0,0]))[0],400)
        self.assertEqual(self.request('/api/jobs',data,Origin='https://other.example')[0],403)
        self.assertEqual(self.request('/api/jobs/notreal')[0],404)
        self.assertEqual(self.request('/../app.py')[0],404)
    def test_preview_rejects_invalid_and_preserves_size(self):
        import base64
        from pathlib import Path
        raw=Path('data/map/hotel.png').read_bytes()
        status,body=self.request('/api/map-preview',{'map_data':base64.b64encode(raw).decode()})
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['width'],240)
        self.assertEqual(self.request('/api/map-preview',{'map_data':'garbage'})[0],400)

if __name__=='__main__':unittest.main()
