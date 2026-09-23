"""Build a screenshot walkthrough from the semantic-import browser checks."""
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
SCENES=[('semantic-review','01  Review pixel classes and map scale'),('semantic-floors','02  Assign images to independent floors'),('semantic-half-link','03  Place both elevator endpoints'),('semantic-planned','04  Preview routes and inspect GA results')]
def main():
    frames=[];font=ImageFont.load_default(size=18)
    for filename,title in SCENES:
        with Image.open(ROOT/'test-artifacts'/f'{filename}.png') as im:
            image=ImageOps.contain(im.convert('RGB'),(960,1000));frame=Image.new('RGB',(960,1040),'#f4f7f9');frame.paste(image,((960-image.width)//2,40));ImageDraw.Draw(frame).text((18,10),title,fill='#284655',font=font);frames.append(frame.quantize(colors=128))
    target=ROOT/'docs/assets/dispatch-demo.gif';frames[0].save(target,save_all=True,append_images=frames[1:],duration=[5500,4000,4500,5000],loop=0,optimize=True)
    with Image.open(target) as im:assert im.n_frames==4
    print(target, target.stat().st_size)
if __name__=='__main__':main()
