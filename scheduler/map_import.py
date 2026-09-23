"""Reviewed raster import. Pixel classes are hypotheses, not physical-map truth.

Classify at source resolution BEFORE conservative block reduction. No eroding,
opening, interpolation or invented elevator endpoints are used in the planner.
"""
from __future__ import annotations
import base64
import binascii
import hashlib
import math
import re
import threading
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from scipy.ndimage import label

# Lower numbers dominate when reducing a block: any wall/unknown blocks the cell.
WALL, UNKNOWN, COST, FREE = 0, 1, 2, 3
CLASS_NAMES = ('wall', 'unknown', 'cost', 'free')
MAX_BYTES = 8_000_000
MAX_PIXELS = 16_000_000
MAX_SIDE = 8192
_lock = threading.BoundedSemaphore(2)


class MapImportError(ValueError):
    def __init__(self, code, **params):
        self.code, self.params = 'semantic.' + code, params
        super().__init__(self.code)


def _number(value, low, high, name, integer=False):
    if isinstance(value, bool):
        raise MapImportError('bad_option', field=name)
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise MapImportError('bad_option', field=name) from None
    if not math.isfinite(n) or not low <= n <= high or (integer and n != int(n)):
        raise MapImportError('bad_option', field=name)
    return int(n) if integer else n


def decode_source(encoded):
    if not isinstance(encoded, str) or len(encoded) > math.ceil(MAX_BYTES / 3) * 4 + 100:
        raise MapImportError('source_size')
    try:
        raw = base64.b64decode(encoded.split(',', 1)[-1], validate=True)
        if len(raw) > MAX_BYTES:
            raise MapImportError('source_size')
        im = Image.open(BytesIO(raw))
        if im.format not in ('PNG', 'JPEG', 'PPM', 'BMP'):
            raise MapImportError('source_format')
        if min(im.size) < 4 or max(im.size) > MAX_SIDE or im.width * im.height > MAX_PIXELS:
            raise MapImportError('source_dimensions')
        # Orient metadata before establishing coordinates; never crop or stretch.
        im = ImageOps.exif_transpose(im)
        return im.convert('RGBA'), hashlib.sha256(raw).hexdigest()
    except (binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise MapImportError('source_format') from None


def options_from(raw):
    if not isinstance(raw, dict):
        raise MapImportError('bad_option', field='options')
    profile = raw.get('profile', 'auto')
    if profile not in ('auto', 'lidar', 'graph', 'floorplan', 'custom'):
        raise MapImportError('bad_option', field='profile')
    inverse = raw.get('invert', False)
    if not isinstance(inverse, bool):
        raise MapImportError('bad_option', field='invert')
    options = dict(profile=profile, invert=inverse,
                   wall_threshold=_number(raw.get('wall_threshold', 100), 0, 253, 'wall_threshold', True),
                   free_threshold=_number(raw.get('free_threshold', 240), 1, 255, 'free_threshold', True),
                   max_side=_number(raw.get('max_side', 512), 64, 512, 'max_side', True))
    if options['wall_threshold'] >= options['free_threshold']:
        raise MapImportError('threshold_order')
    rules = raw.get('rules', [])
    if not isinstance(rules, list) or len(rules) > 12:
        raise MapImportError('bad_option', field='rules')
    result = []
    for rule in rules:
        if not isinstance(rule, dict) or rule.get('kind') not in CLASS_NAMES:
            raise MapImportError('bad_option', field='rule')
        color = rule.get('color')
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise MapImportError('bad_option', field='color')
        result.append(dict(color=color, kind=rule['kind'], tolerance=_number(rule.get('tolerance', 8), 0, 64, 'tolerance', True)))
    options['rules'] = result
    return options


def classify(image, options):
    a = np.asarray(image, dtype=np.uint8)
    rgb = a[:, :, :3]
    gray = np.asarray(image.convert('L'))
    if options['invert']:
        gray = 255 - gray
    opaque = a[:, :, 3] == 255  # semitransparency is also unobserved, never free
    colored = np.ptp(rgb, axis=2) > 20
    mid = (gray > options['wall_threshold']) & (gray < options['free_threshold']) & opaque
    opaque_count = max(1, int(opaque.sum()))
    mid_fraction = float(mid.sum() / opaque_count)
    requested = options['profile']
    # Histogram-based suggestion only. User must review the segmentation.
    profile = ('lidar' if mid_fraction > .02 else 'floorplan') if requested == 'auto' else requested
    classes = np.full(gray.shape, UNKNOWN, dtype=np.uint8)
    if profile != 'custom':
        classes[gray <= options['wall_threshold']] = WALL
        classes[(gray >= options['free_threshold']) & ~colored] = FREE
        if profile == 'floorplan':
            classes[mid & ~colored] = COST
    if options['rules']:
        chosen = np.full(gray.shape, 4, dtype=np.uint8)
        rgb16 = rgb.astype(np.int16)
        for rule in options['rules']:
            color = np.array([int(rule['color'][i:i+2], 16) for i in (1, 3, 5)], dtype=np.int16)
            matches = np.max(np.abs(rgb16 - color), axis=2) <= rule['tolerance']
            chosen[matches] = np.minimum(chosen[matches], CLASS_NAMES.index(rule['kind']))
        changed = chosen < 4
        classes[changed] = chosen[changed]
    # Explicit swatches cannot free a transparent pixel. Mixed-class rule overlaps
    # are deterministic: wall > unknown > costly > free.
    classes[~opaque] = UNKNOWN
    counts = {name: int((classes == k).sum()) for k, name in enumerate(CLASS_NAMES)}
    hist = np.bincount(gray[opaque].ravel(), minlength=256)
    dominant = np.argsort(hist)[-5:][::-1]
    return classes, dict(profile=profile, mid_fraction=mid_fraction,
                        colored_fraction=float(colored.mean()), counts=counts,
                        histogram=[dict(gray=int(k), count=int(hist[k])) for k in dominant if hist[k]])


def reduce_classes(classes, factor):
    """Min-pool categories; partial edge blocks are padded UNKNOWN, not stretched."""
    h, w = classes.shape
    ph, pw = math.ceil(h/factor)*factor, math.ceil(w/factor)*factor
    a = np.pad(classes, ((0, ph-h), (0, pw-w)), constant_values=UNKNOWN)
    return a.reshape(ph//factor, factor, pw//factor, factor).min(axis=(1, 3))


def png(image):
    b = BytesIO(); image.save(b, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()


def review_map(data):
    if not isinstance(data, dict):
        raise MapImportError('bad_option', field='request')
    if not _lock.acquire(blocking=False):
        raise MapImportError('busy')
    try:
        image, digest = decode_source(data.get('map_data'))
        if 'sample' in data:
            point = data['sample']
            if not isinstance(point, dict):
                raise MapImportError('bad_option', field='sample')
            x = _number(point.get('x'), 0, image.width-1, 'x', True)
            y = _number(point.get('y'), 0, image.height-1, 'y', True)
            rgba = image.getpixel((x, y))
            return dict(color='#' + ''.join(f'{v:02x}' for v in rgba[:3]), alpha=rgba[3], x=x, y=y)
        options = options_from(data.get('options', {}))
        source_resolution = _number(data.get('source_resolution', .1), .001, 2, 'source_resolution')
        factor = math.ceil(max(image.size)/options['max_side'])
        resolution = source_resolution*factor
        if resolution > 2:
            raise MapImportError('scale_limit')
        classes, analysis = classify(image, options)
        reduced = reduce_classes(classes, factor)
        # Same raster consumed by Costmap: unknown and wall are both hard blocked.
        pixels = np.take(np.array([0, 0, 200, 255], dtype=np.uint8), reduced)
        from .core import Costmap
        settings = data.get('settings', {})
        if not isinstance(settings, dict):
            raise MapImportError('bad_option', field='settings')
        radius = _number(settings.get('radius', .2), 0, 2, 'radius')
        threshold = _number(settings.get('threshold', 100), 0, 254, 'threshold', True)
        gray_cost = _number(settings.get('gray_cost', 2), 0, 10, 'gray_cost')
        grid = Costmap(pixels, resolution, threshold, radius, gray_cost)
        cc, count = label(~grid.blocked)
        sizes = np.bincount(cc.ravel()); largest = int(sizes[1:].max()) if count else 0
        palette = np.array([[25,31,38],[225,183,108],[162,173,186],[247,250,252]], dtype=np.uint8)
        class_image = Image.fromarray(palette[reduced])
        # Resampling below is for visual comparison only, never planner occupancy.
        thumb = image.copy(); thumb.thumbnail((900,600))
        warnings = ['review_required']
        if factor > 1: warnings.append('reduced')
        if analysis['colored_fraction'] > .001: warnings.append('colored')
        if not largest: warnings.append('no_free')
        elif count > 1: warnings.append('components')
        return dict(model='semantic-import-v1', source_size=list(image.size), source_sha256=digest,
                    factor=factor, width=grid.width, height=grid.height, resolution=resolution,
                    source_resolution=source_resolution, options=options, analysis=analysis,
                    map_data=png(Image.fromarray(pixels)), source_preview=png(thumb),
                    class_preview=png(class_image),
                    clearance_preview=png(Image.fromarray(np.where(grid.blocked, 0, pixels).astype(np.uint8))),
                    blocked_rows=[''.join('1' if v else '0' for v in row) for row in grid.blocked],
                    stats=dict(walkable=int((~grid.blocked).sum()), cells=int(pixels.size),
                               components=int(count), largest_component=largest,
                               counts={name:int((reduced == k).sum()) for k,name in enumerate(CLASS_NAMES)}),
                    warnings=warnings)
    finally:
        _lock.release()


def reference_maps():
    """Local, pinned repository images; runtime never fetches arbitrary URLs."""
    root = Path(__file__).resolve().parents[1] / 'data/reference_maps'
    return [dict(id=p.stem, filename=p.name) for p in sorted(root.glob('map_*.png'))]


def reference_map(map_id):
    records = {r['id']:r for r in reference_maps()}
    if map_id not in records:
        raise MapImportError('reference_missing')
    name = records[map_id]['filename']
    raw = (Path(__file__).resolve().parents[1]/'data/reference_maps'/name).read_bytes()
    return dict(filename=name, map_data='data:image/png;base64,'+base64.b64encode(raw).decode())
