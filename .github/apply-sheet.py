"""One-time exact-source integration for the reviewed Sheet workbench.

Edits use Unicode string offsets against hash-verified source files. Every output
is checked against the locally tested SHA-256 before any test or publication.
This helper and its inputs are removed before the final branch commit.
"""
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=json.loads((ROOT/'.github/sheet-manifest.json').read_text())

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def target(name):
    path=(ROOT/name).resolve()
    if name not in MANIFEST or not path.is_relative_to(ROOT):
        raise ValueError('Unexpected integration path: '+name)
    return path

def verify():
    for name,expected in MANIFEST.items():
        actual=digest(target(name))
        if actual!=expected:raise ValueError(f'Output mismatch: {name}: {actual} != {expected}')
    print(f'Exact source verification: {len(MANIFEST)} files match locally tested hashes.',flush=True)

if '--publish' in sys.argv:
    verify()
    archive=ROOT/'test-artifacts';archive.mkdir(exist_ok=True)
    (archive/'published-manifest.json').write_text(json.dumps(MANIFEST,indent=2)+'\n')
    subprocess.run(['git','add','--',*MANIFEST,'docs/assets/dispatch-demo.gif'],cwd=ROOT,check=True)
    temporary=['.github/apply-sheet.py','.github/sheet-edits.json','.github/sheet-tests-edits.json',
               '.github/sheet-catalogue.json','.github/sheet-docs.py','.github/sheet-manifest.json',
               '.github/workflows/sheet-workbench-check.yml']
    subprocess.run(['git','rm','--',*temporary],cwd=ROOT,check=True)
    subprocess.run(['git','commit','-m','Ship verified Sheet workbench, channel dragging and refreshed walkthrough'],cwd=ROOT,check=True)
    subprocess.run(['git','push','origin','HEAD:refs/heads/feature/sheet-first-workbench'],cwd=ROOT,check=True)
    subprocess.run(['git','archive','--format=zip','--output=sheet-verified-source.zip','HEAD'],cwd=ROOT,check=True)
elif '--check' in sys.argv:
    verify()
else:
    pending=[]
    for filename in ['sheet-edits.json','sheet-tests-edits.json']:
        for name,spec in json.loads((ROOT/'.github'/filename).read_text()).items():
            path=target(name)
            if digest(path)==spec['sha256']:continue
            if digest(path)!=spec['base_sha256']:raise ValueError('Base mismatch: '+name)
            original=path.read_text(encoding='utf-8');updated=original;previous=0
            for e in spec['edits']:
                if not previous<=e['start']<=e['end']<=len(original):raise ValueError('Invalid edit range')
                previous=e['end']
            for e in reversed(spec['edits']):updated=updated[:e['start']]+e['text']+updated[e['end']:]
            if hashlib.sha256(updated.encode()).hexdigest()!=spec['sha256']:raise ValueError('Edit mismatch: '+name)
            pending.append((path,updated))
    for path,updated in pending:path.write_text(updated,encoding='utf-8')
    path=target('web/locales.json');catalogue=json.loads(path.read_text())
    for language,updates in json.loads((ROOT/'.github/sheet-catalogue.json').read_text()).items():
        catalogue[language].update(updates)
    path.write_text(json.dumps(catalogue,ensure_ascii=False,indent=2)+'\n')
    if any(digest(target(name))!=MANIFEST[name] for name in ['README.md','docs/guide.md','docs/semantic_maps.md']):
        runpy.run_path(str(ROOT/'.github/sheet-docs.py'))
    # Native navigation exposes an asynchronous test race: an earlier preview
    # can be ready while the new blank-sheet HTTP request is still pending.
    # Wait for that action's completion too; assertions and production code stay intact.
    path=target('tests/browser_workbench.py')
    if digest(path)!=MANIFEST['tests/browser_workbench.py']:
        if digest(path)!='e494d5dd674588d5f1e8073b4b4a8479eccfc6c16b1cb5b4a6eaddb1ed731eba':
            raise ValueError('Unexpected browser test source')
        old="def ready():wait('!!preview && !previewRunning && !previewQueued')"
        new="def ready():wait('!!preview && !previewRunning && !previewQueued && !uploadInProgress && !mapApplying')"
        text=path.read_text()
        if text.count(old)!=1:raise ValueError('Expected exactly one readiness helper')
        path.write_text(text.replace(old,new))
    verify()
