"""Build the README GIF from real browser acceptance screenshots.

Run tests/browser_workbench.py first. Frames are screenshots, not a continuous
screen recording. This script adds only captions and letterboxing, not UI data.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SCENES = [
    ('sheet-first.png', '01  Start with one sheet', 3000),
    ('sheet-import.png', '02  Review the map. Use it.', 3500),
    ('sheet-channels.png', '03  Connect entrances, not delivery stops', 3500),
    ('sheet-dragging.png', '04  Drag channel handles across sheets', 3000),
    ('sheet-evolution-focus.png', '05  Explore real generations and elites', 4500),
]


def main():
    frames = []
    width, height, header = 1080, 820, 42
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', 19)
    except OSError:
        font = ImageFont.load_default()
    for filename, caption, _ in SCENES:
        with Image.open(ROOT / 'test-artifacts' / filename) as source:
            im = source.convert('RGB')
        im.thumbnail((width, height - header), Image.Resampling.LANCZOS)
        frame = Image.new('RGB', (width, height), '#f0f5fb')
        frame.paste(im, ((width - im.width) // 2, header + (height - header - im.height) // 2))
        ImageDraw.Draw(frame).text((20, 10), caption, font=font, fill='#193b57')
        frames.append(frame.quantize(colors=256, method=Image.Quantize.MEDIANCUT))
    output = ROOT / 'docs' / 'assets' / 'dispatch-demo.gif'
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(output, save_all=True, append_images=frames[1:], duration=[s[2] for s in SCENES],
                   loop=0, disposal=2, optimize=False)
    with Image.open(output) as check:
        assert check.n_frames == len(SCENES)
        assert check.size == (width, height)
    print(f'{output.relative_to(ROOT)}: {output.stat().st_size} bytes, {sum(s[2] for s in SCENES)/1000:g} seconds')


if __name__ == '__main__':
    main()
