"""Generate reproducible grayscale occupancy examples, without artistic pixels."""
from pathlib import Path
from PIL import Image, ImageDraw
import json

ROOT=Path(__file__).resolve().parents[1]

def generate():
    target=ROOT/'data/map';target.mkdir(parents=True,exist_ok=True)
    for name in ('hotel','restaurant','warehouse'):
        im=Image.new('L',(240,160),255); d=ImageDraw.Draw(im)
        d.rectangle((0,0,239,159),outline=0,width=4)
        if name=='hotel':
            # Central corridor, rooms with wide doors opening into it.
            for y in (55,105):
                d.rectangle((4,y,235,y+3),fill=0)
                for x in (28,73,118,163,208): d.rectangle((x-7,y,x+7,y+3),fill=255)
            for x in (50,95,140,185):
                d.rectangle((x,4,x+3,54),fill=0);d.rectangle((x,109,x+3,155),fill=0)
            d.rectangle((98,65,140,94),fill=205)
            points=[(28,28),(73,28),(118,28),(163,28),(208,28),(208,130),(163,130),(118,130),(73,130),(28,130)]
            start=[15,80]
        elif name=='restaurant':
            d.rectangle((5,5,60,45),fill=0)
            for x in (85,130,175,215):
                for y in (35,80,125): d.rectangle((x-9,y-7,x+9,y+7),fill=0)
            d.rectangle((10,62,48,130),fill=215)
            points=[(70,35),(115,35),(160,35),(200,35),(200,100),(160,125),(115,125),(65,125)]
            start=[22,145]
        else:
            for x in (45,85,125,165,205):
                d.rectangle((x,25,x+14,130),fill=0)
            d.rectangle((65,5,155,17),fill=195)
            points=[(30,40),(72,40),(112,40),(152,40),(195,40),(225,120),(152,120),(72,120)]
            start=[15,145]
        im.save(target/f'{name}.png')
        (target/f'{name}.json').write_text(json.dumps({'start':start,'points':points,'resolution':.1},indent=2))

if __name__=='__main__': generate()
