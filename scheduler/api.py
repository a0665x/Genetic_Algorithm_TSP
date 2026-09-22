"""Validation and background-job orchestration shared by the HTTP API and tests."""
import base64
import binascii
from io import BytesIO
from pathlib import Path
import math
import threading
import time
import uuid
from PIL import Image, UnidentifiedImageError
from .core import Costmap, Order, prepare, weights, Objective, evolve

ROOT=Path(__file__).resolve().parents[1]
MAPS={'hotel':'飯店客房層','restaurant':'餐廳與用餐區','warehouse':'倉儲貨架'}
MAX_IMAGE_BYTES=2_000_000


def number(value,name,low,high,integer=False):
    if isinstance(value,bool): raise ValueError(f'{name} 必須是數值。')
    try: f=float(value)
    except (TypeError,ValueError): raise ValueError(f'{name} 必須是數值。')
    if not math.isfinite(f) or not low<=f<=high or (integer and f!=int(f)):
        raise ValueError(f'{name} 必須介於 {low}–{high}'+('，且為整數。' if integer else '。'))
    return int(f) if integer else f


def image_from_request(data):
    if not isinstance(data,dict): raise ValueError('地圖請求需為 JSON 物件。')
    if data.get('map_data') is not None and not isinstance(data['map_data'],str): raise ValueError('map_data 必須是 base64 字串。')
    if data.get('map_data'):
        try:
            encoded=data['map_data'].split(',',1)[-1]
            if len(encoded)>MAX_IMAGE_BYTES*1.4: raise ValueError('圖片檔案過大，請使用 2 MB 以下圖片。')
            raw=base64.b64decode(encoded,validate=True)
            im=Image.open(BytesIO(raw))
            if im.format not in ('PNG','JPEG','PPM','BMP'): raise ValueError('請上傳 PNG、JPG、PGM 或 BMP 地圖。')
            if min(im.size)<4 or max(im.size)>512: raise ValueError('地圖每邊需為 4–512 px，程式不會自動縮圖以免消除細牆。')
            rgba=im.convert('RGBA'); bg=Image.new('RGBA',im.size,'black'); bg.alpha_composite(rgba)
            return bg.convert('L')
        except (binascii.Error,UnidentifiedImageError,OSError,Image.DecompressionBombError) as e:
            raise ValueError('無法讀取地圖圖片。') from e
    name=data.get('map','hotel')
    if name not in MAPS: raise ValueError('未知範例地圖。')
    return Image.open(ROOT/'data/map'/f'{name}.png').convert('L')


def validate(data):
    if not isinstance(data,dict): raise ValueError('請提供 JSON 物件。')
    cfg=data.get('settings',{})
    if not isinstance(cfg,dict): raise ValueError('settings 格式錯誤。')
    spec={'resolution':(.1,.01,2,False),'radius':(.2,0,2,False),'threshold':(100,0,254,True),
          'gray_cost':(2,0,10,False),'cruise':(.8,.05,3,False),'local_radius':(1,0,10,False),
          'population':(60,10,200,True),'generations':(80,1,300,True),'worlds':(4,1,8,True),
          'interval':(10,1,100,True),'migration':(.15,0,.5,False),'mutation':(.2,0,1,False),
          'seed':(42,0,2147483647,True),'priority':(1,0,20,False),'risk_penalty':(120,0,2000,False),
          'distance_penalty':(1,0,20,False)}
    settings={k:number(cfg.get(k,d),k,lo,hi,integer) for k,(d,lo,hi,integer) in spec.items()}
    for k,d in [('sower',True),('return_to_start',True)]:
        if not isinstance(cfg.get(k,d),bool): raise ValueError(f'{k} 必須是布林值。')
        settings[k]=cfg.get(k,d)
    settings['mode']=cfg.get('mode','operational')
    if settings['mode'] not in ('operational','disclosure'): raise ValueError('評分模式不正確。')
    if settings['population']*settings['generations']*(settings['worlds'] if settings['sower'] else 1)>300000:
        raise ValueError('互動計算預算上限為 300,000 個候選；請降低世代、族群或世界數。')
    coefficients=data.get('coefficients',{})
    if not isinstance(coefficients,dict): raise ValueError('權重係數格式錯誤。')
    from .core import DEFAULT_COEFFICIENTS
    c={k:number(coefficients.get(k,v),k,-10 if k=='bias' else 0,10) for k,v in DEFAULT_COEFFICIENTS.items()}
    def point(p,label):
        if not isinstance(p,(list,tuple)) or len(p)!=2: raise ValueError(f'請在地圖上設定{label}。')
        return tuple(number(v,label,0,511,True) for v in p)
    start=point(data.get('start'),'起點'); end=point(data['end'],'終點') if data.get('end') is not None else None
    raw=data.get('orders',[])
    if not isinstance(raw,list) or not 1<=len(raw)<=30: raise ValueError('請設定 1–30 筆訂單。')
    orders=[]; ids=set()
    for o in raw:
        if not isinstance(o,dict): raise ValueError('訂單格式錯誤。')
        id=o.get('id','')
        if not isinstance(id,str) or not id.strip() or len(id)>40 or id in ids: raise ValueError('訂單 ID 必須唯一、非空且不超過 40 字。')
        ids.add(id); x,y=point([o.get('x'),o.get('y')],id)
        forbidden=o.get('forbidden',[])
        if not isinstance(forbidden,list): raise ValueError('禁止順位需為整數陣列。')
        forbidden=tuple(number(v,'禁止順位',1,len(raw),True) for v in forbidden)
        values={k:number(o.get(k,d),f'{id} {k}',lo,hi) for k,d,lo,hi in [
            ('importance',5,0,10),('waited',0,0,86400),('patience',300,1,86400),
            ('risk',.5,0,1),('speed',.8,.05,3),('service',10,0,3600)]}
        orders.append(Order(id,x,y,**values,forbidden=forbidden))
    grid=Costmap(image_from_request(data),settings['resolution'],settings['threshold'],settings['radius'],settings['gray_cost'])
    # Validate constraints before expensive A* preprocessing.
    import random
    from .core import repair
    repair(tuple(range(len(orders))),orders,random.Random(settings['seed']))
    for label,p in [('起點',start)]+[(o.id,(o.x,o.y)) for o in orders]+([] if end is None else [('終點',end)]):
        if not grid.valid(p): raise ValueError(f'{label} {p} 位於障礙物、安全膨脹區或地圖外。')
    return grid,orders,start,end,settings,c


class Jobs:
    validate = staticmethod(validate)
    def __init__(self):
        self.items={};self.lock=threading.RLock()
    def start(self,data):
        validated=self.validate(data)
        with self.lock:
            now=time.time()
            self.items={k:v for k,v in self.items.items() if v['status'] in ('running','queued') or now-v['created']<1800}
            if any(v['status'] in ('running','queued') for v in self.items.values()): raise ValueError('已有規劃執行中，請先停止或等待完成。')
            # Bound retained replay memory even for repeated short jobs.
            while len(self.items)>=5: self.items.pop(next(iter(self.items)))
            id=uuid.uuid4().hex
            self.items[id]={'status':'queued','phase':'準備地圖','history':[],'progress':0,'error':None,'created':now,'cancel':threading.Event()}
        threading.Thread(target=self._run,args=(id,validated),daemon=True).start()
        return id
    def _run(self,id,v):
        grid,orders,start,end,cfg,c=v
        item=self.items[id];cancelled=item['cancel'].is_set
        def update(**kwargs):
            with self.lock: item.update(kwargs)
        try:
            update(status='running',phase='A* 計算節點間避牆路徑')
            m=prepare(grid,orders,start,end,cfg['cruise'],cfg['local_radius'],lambda done,total:update(progress=round(25*done/total,1)),cancelled)
            rows=weights(orders,m,cfg['cruise'],c)
            priority_matrix=[[0. if i==j or j==0 or j>len(orders) else rows[j-1]['weight'] for j in range(len(m['points']))] for i in range(len(m['points']))]
            meta={'weights':rows,'points':m['points'],'paths':m['paths'],'distance_matrix':m['distance'].tolist(),'time_matrix':m['travel'].tolist(),'weight_matrix':priority_matrix,'labels':['START']+[o.id for o in orders]+([] if end is None else ['END'])}
            update(meta=meta,phase='GA 世代競爭與 Sower 菁英交換')
            obj=Objective(orders,m,rows,cfg['return_to_start'],end is not None,cfg['priority'],cfg['risk_penalty'],cfg['distance_penalty'],cfg['mode'])
            def callback(record):
                with self.lock:
                    item['history'].append(record);item['progress']=25+75*record['generation']/cfg['generations']
            result=evolve(obj,**{k:cfg[k] for k in ('population','generations','worlds','sower','interval','migration','mutation','seed')},callback=callback,cancelled=cancelled)
            result.pop('history')
            update(status='done',phase='完成',progress=100,result=result,elapsed=round(time.time()-item['created'],2))
        except InterruptedError as e: update(status='cancelled',error=str(e),phase='已停止')
        except ValueError as e: update(status='error',error=str(e),phase='無法規劃')
        except Exception:
            import traceback
            traceback.print_exc();update(status='error',error='內部計算錯誤；詳情請查看終端機。',phase='計算失敗')
    def get(self,id,after=0):
        with self.lock:
            if id not in self.items: raise KeyError(id)
            item=self.items[id]
            result={k:v for k,v in item.items() if k not in ('history','cancel','created','meta')}
            result['history']=item['history'][after:];result['count']=len(item['history'])
            if 'meta' in item and after==0: result['meta']=item['meta']
            return result
    def cancel(self,id):
        with self.lock:
            if id not in self.items: raise KeyError(id)
            self.items[id]['cancel'].set()
