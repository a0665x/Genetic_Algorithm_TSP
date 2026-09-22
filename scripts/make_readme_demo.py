#!/usr/bin/env python3
"""Build the README GIF from screenshots produced by tests/browser_studio.py."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageSequence

ROOT = Path(__file__).resolve().parents[1]
DURATIONS = [3600, 3200, 4000, 4200]


def font(size: int, bold: bool = False):
    try:
        return ImageFont.truetype(
            'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf', size
        )
    except OSError:
        return ImageFont.load_default(size=size)


def build(source: Path, output: Path, width: int = 800) -> None:
    screenshots = []
    for name in ('studio-plan.png', 'studio-building.png', 'studio-math.png'):
        with Image.open(source / name) as image:
            if image.size != (1440, 1200):
                raise ValueError(f'{name}: expected a 1440x1200 browser screenshot')
            screenshots.append(image.convert('RGB'))

    scale = width / 1440
    height, header = round(960 * scale), 54
    views = [
        image.crop((0, 80, 1440, 1040)).resize(
            (width, height), Image.Resampling.LANCZOS
        )
        for image in screenshots[:2]
    ]
    # Focus the calculation dialog on the matrix and selected path details.
    matrix = screenshots[2].crop((260, 10, 1180, 785)).resize(
        (round(920 * scale), round(775 * scale)), Image.Resampling.LANCZOS
    )
    detail = Image.new('RGB', (width, height), '#f3f6f8')
    detail.paste(matrix, ((width - matrix.width) // 2, (height - matrix.height) // 2))
    views.append(detail)

    captions = (
        '1  Set order priorities',
        '2  Review the planned route',
        '3  Explore floors and elevators',
        '4  Inspect travel-time details',
    )
    frames = []
    for index, (view, caption) in enumerate(zip([views[0], views[0], views[1], views[2]], captions)):
        frame = Image.new('RGB', (width, height + header), 'white')
        frame.paste(view, (0, header))
        draw = ImageDraw.Draw(frame)
        draw.text((18, 10), caption, fill='#123343', font=font(18, bold=True))
        draw.text((width - 160, 16), 'UI walkthrough', fill='#647782', font=font(12))
        draw.line((0, header - 1, width, header - 1), fill='#dce6e9')
        if index == 0:
            draw.rounded_rectangle(
                (round(1174 * scale), round(19 * scale) + header,
                 round(1416 * scale), round(417 * scale) + header),
                radius=6, outline='#078499', width=2,
            )
        frames.append(frame)

    # Preserve wall black and route/elevator accents in a compact shared palette.
    colors = (
        '#ffffff', '#fafbfd', '#f3f6f8', '#e5edf1', '#cbd8de', '#aab9c1',
        '#8195a1', '#536f83', '#183143', '#050505', '#008895', '#bde4e8',
        '#4e65da', '#ce863b', '#3c955b', '#777777',
    )
    rgb = [int(color[i:i + 2], 16) for color in colors for i in (1, 3, 5)]
    palette = Image.new('P', (1, 1))
    palette.putpalette(rgb + [0] * (768 - len(rgb)))
    indexed = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    output.parent.mkdir(parents=True, exist_ok=True)
    indexed[0].save(
        output, save_all=True, append_images=indexed[1:], duration=DURATIONS,
        loop=0, disposal=1, optimize=True,
    )
    with Image.open(output) as result:
        assert result.n_frames == 4 and result.info.get('loop') == 0
        assert sum(frame.info['duration'] for frame in ImageSequence.Iterator(result)) == 15000
    print(f'{output}: {width}x{height + header}, 4 frames, 15s, {output.stat().st_size:,} bytes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'test-artifacts')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/assets/dispatch-demo.gif')
    parser.add_argument('--width', type=int, choices=range(640, 1601), default=800, metavar='640..1600')
    args = parser.parse_args()
    try:
        build(args.source, args.output, args.width)
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\nGenerate the screenshots with python tests/browser_studio.py first.\n')
