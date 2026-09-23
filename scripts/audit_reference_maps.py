"""Audit a local folder of reference images, without modifying those images."""
import argparse
import base64
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scheduler.map_import import review_map

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);p.add_argument('--output',type=Path,default=ROOT/'test-artifacts/source-map-audit.json');args=p.parse_args()
    records=[]
    for image in sorted(args.folder.rglob('*')):
        if image.suffix.lower() not in ('.png','.jpg','.jpeg','.pgm','.bmp'):continue
        raw=base64.b64encode(image.read_bytes()).decode()
        r=review_map(dict(map_data=raw,source_resolution=.1))
        records.append(dict(file=str(image.relative_to(args.folder)),source_size=r['source_size'],source_sha256=r['source_sha256'],factor=r['factor'],grid=[r['width'],r['height']],analysis=r['analysis'],stats=r['stats'],warnings=r['warnings']))
    if not records:raise SystemExit('No image files found')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(dict(scale_note='0.1 source m/px is a test assumption, not measured calibration',images=records),indent=2))
    print(f'{len(records)} images audited: {args.output}')
if __name__=='__main__':main()
