"""Export the built-in synthetic Studio scenario; no additional dependencies."""
import base64
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scheduler.building import demo_scene

if __name__=='__main__':
    target=ROOT/'test-artifacts'/'studio-demo'
    target.mkdir(parents=True,exist_ok=True)
    scene=demo_scene()
    for floor in scene['floors']:
        (target/f"{floor['id']}.png").write_bytes(base64.b64decode(floor['map_data'].split(',',1)[1]))
    (target/'scene.json').write_text(json.dumps(scene,indent=2,ensure_ascii=False))
    print(target)
