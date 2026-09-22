"""Assemble an actual-UI screenshot walkthrough after the browser acceptance tests."""
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SCENES = [
    ('editor-preview', '01  Edit nodes and preview routes'),
    ('portals-pair-editor', '02  Pair elevator endpoints'),
    ('portals-half-english', '03  Repair incomplete elevator links'),
    ('editor-evolution', '04  Inspect GA evolution and elites'),
]


def build():
    frames = []
    font = ImageFont.load_default(size=19)
    for name, title in SCENES:
        with Image.open(ROOT / 'test-artifacts' / f'{name}.png') as source:
            # Scale full actual screenshots; do not replace controls or route data.
            image = ImageOps.contain(source.convert('RGB'), (960, 1000))
            frame = Image.new('RGB', (960, 1040), '#f4f7f9')
            frame.paste(image, ((960-image.width)//2, 40))
            ImageDraw.Draw(frame).text((20, 10), title, fill='#284655', font=font)
            frames.append(frame.quantize(colors=128, method=Image.Quantize.MEDIANCUT))
    target = ROOT / 'docs/assets/dispatch-demo.gif'
    target.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(target, save_all=True, append_images=frames[1:],
                   duration=[3500, 4500, 4500, 5000], loop=0, optimize=True)
    with Image.open(target) as check:
        assert check.n_frames == len(SCENES)
    print(f'{target}: {target.stat().st_size} bytes')


if __name__ == '__main__':
    build()
