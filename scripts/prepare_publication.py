"""Inventory project sources and assets without copying multi-gigabyte caches.

Git retains source, documentation, web UI, fonts and current films. Rebuildable
frame/solver caches stay local. The release restores the remaining site assets
and non-sequential research inputs at their original relative paths.
"""
from pathlib import Path
import collections
import hashlib
import json
import os
import re

ROOT = Path(__file__).resolve().parents[1]
TAG = 'v0.1.0'
CODE = {'.py','.js','.mjs','.cjs','.ts','.html','.css','.wgsl','.glsl','.cpp','.h',
        '.md','.toml','.bat','.ps1','.sh','.feat','.txt','.csv','.yaml','.yml'}
MEDIA = {'.mp4','.mov','.webm','.zip','.gz','.npz','.npy','.f32','.bin','.blend',
         '.gltf','.obj','.ply','.ttf','.woff','.woff2','.svg','.png','.jpg','.jpeg'}
SKIP_DIRS = {'node_modules','__pycache__','.git','.venv','venv','temp','warp-cache',
             'lossless-frame-archives','rejected-flat-ice-frames'}
CURRENT = {'fire-02.mp4','water-02-r8.mp4','earth-02-r6.mp4','air-02.mp4',
           'ice-02.mp4','lava-02.mp4','lightning-02-r5.mp4',
           'water-02-r7.mp4','earth-02-r5.mp4','lightning-02-r4.mp4'}

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def main():
    tracked, assets, excluded = [], [], collections.Counter()
    inode_hashes = {}
    for top in ['outputs','work']:
        for base, dirs, files in os.walk(ROOT / top):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith('tmp'))
            for name in sorted(files):
                p = Path(base) / name
                rel = p.relative_to(ROOT).as_posix()
                ext = p.suffix.lower()
                if top == 'work' and '/publication/' in rel:
                    continue
                try:
                    stat = p.stat()
                except OSError:
                    excluded['unreadable temporary files'] += 1
                    continue
                if ext in CODE or name.upper().startswith('LICENSE'):
                    if ext == '.txt' and ('log' in name or stat.st_size > 1024**2):
                        excluded['logs'] += 1
                    else:
                        tracked.append(rel)
                    continue
                if top == 'outputs':
                    if ext not in {'.mp4','.webm','.mov','.zip','.gz','.f32','.bin','.npz','.npy'}:
                        tracked.append(rel)
                        continue
                    if '/sigils/02/' in rel and name in CURRENT:
                        tracked.append(rel)
                        continue
                else:
                    parts = [s.lower() for s in p.relative_to(ROOT / 'work').parts[:-1]]
                    cache = any(s in {'cache','particles','meshes','frames','density','vdb','atlases'}
                                or s.endswith(('-frames','-density')) or s.startswith('air-density-') for s in parts)
                    sequential = bool(re.search(r'(?:^|[-_])\d{3,}(?:\D|$)', name))
                    if name.endswith(('.pt.gz','.log.gz')) or ext in {'.log','.pt','.uni','.particles','.shape','.vdb','.exr','.pyc'} or cache or sequential:
                        excluded['rebuildable frames and simulation caches'] += 1
                        continue
                    if ext == '.json' and stat.st_size <= 256*1024:
                        tracked.append(rel)
                        continue
                    if ext in {'.png','.jpg','.jpeg'} and not any(k in rel.lower() for k in
                            ['source','mask','approved','reference','scans/','brand-font/','texture','fuel','arrival']):
                        excluded['intermediate review images'] += 1
                        continue
                    if ext not in MEDIA | {'.json'}:
                        excluded['temporary or generated data'] += 1
                        continue
                digest = inode_hashes.setdefault(stat.st_ino, None)
                if digest is None:
                    digest = sha(p)
                    inode_hashes[stat.st_ino] = digest
                assets.append({'path':rel, 'bytes':stat.st_size, 'sha256':digest})
    # Preserve the final verification receipts even when their location is a cache.
    for p in (ROOT/'work/element-motion/sigil-02-active-elements').rglob('*audit.json'):
        if p.stat().st_size < 256*1024:
            tracked.append(p.relative_to(ROOT).as_posix())
    tracked = sorted(set(tracked))
    assets = [a for a in assets if a['path'] not in set(tracked)]
    unique = {}
    for a in assets:
        unique.setdefault(a['sha256'], a)
    plans = []
    group, size = [], 0
    for a in sorted(unique.values(), key=lambda a:a['path']):
        if group and size + a['bytes'] > 96*1024**2:
            plans.append(group); group=[]; size=0
        group.append(a); size += a['bytes']
    if group:
        plans.append(group)
    mapping = {}
    packs = []
    for i, group in enumerate(plans, 1):
        name = f'project-assets-{i:03}.zip'
        packs.append({'name':name, 'files':group, 'uncompressedBytes':sum(a['bytes'] for a in group)})
        for a in group:
            mapping[a['sha256']] = {'pack':name, 'member':a['path']}
    for a in assets:
        a.update(mapping[a['sha256']])
    out = ROOT/'docs'
    out.mkdir(exist_ok=True)
    manifest = {'version':1, 'repository':'cybrdelic/cybr-elements', 'tag':TAG,
                'assets':assets, 'packs':[{k:v for k,v in p.items() if k!='files'} for p in packs]}
    (out/'assets.json').write_text(json.dumps(manifest, indent=2)+'\n')
    plan = {'tracked':tracked, 'packs':packs, 'excludedCategories':dict(excluded)}
    (ROOT/'work/publication').mkdir(exist_ok=True)
    (ROOT/'work/publication/plan.json').write_text(json.dumps(plan, indent=2))
    stats = {'gitFiles':len(tracked), 'gitMiB':round(sum((ROOT/p).stat().st_size for p in tracked)/1024**2,1),
             'releasePaths':len(assets),'uniqueAssets':len(unique),'packs':len(packs),
             'releaseMiB':round(sum(a['bytes'] for a in unique.values())/1024**2,1),
             'excludedCategories':dict(excluded)}
    (out/'publication-scope.json').write_text(json.dumps(stats, indent=2)+'\n')
    print(json.dumps(stats, indent=2))

if __name__ == '__main__':
    main()
