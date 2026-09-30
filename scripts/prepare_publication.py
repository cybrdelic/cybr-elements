"""Inventory project sources and assets without copying multi-gigabyte caches.

Git retains source, documentation, web UI, fonts and current films. Rebuildable
frame/solver caches stay local. The release restores the remaining site assets
and non-sequential research inputs at their original relative paths. New release
plans are staged in work/publication; published docs are never overwritten here.
"""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import os
import re
import fetch_assets

ROOT = Path(__file__).resolve().parents[1]
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

def prepare(tag, repository='cybrdelic/cybr-elements'):
    # An ordinary clone contains only a fraction of the full release inventory.
    # Do not silently turn that partial checkout into the next release manifest.
    previous = fetch_assets.safe_target('docs/assets.json', ROOT)
    if previous.exists():
        manifest = fetch_assets.validate_manifest(json.loads(previous.read_text(encoding='utf-8')))
        if tag == manifest['tag'] and any('sha256' in pack for pack in manifest['packs']):
            raise ValueError('Choose a new release tag; the existing release manifest is immutable.')
        missing = []
        for asset in manifest['assets']:
            source = fetch_assets.safe_target(asset['path'], ROOT)
            if not source.is_file():
                missing.append(asset['path'])
        if missing:
            raise ValueError(f'{len(missing)} released inputs are missing. Run python scripts/fetch_assets.py --all before preparing a complete release.')
    fetch_assets.validate_manifest({'version': 1, 'repository': repository, 'tag': tag, 'assets': [], 'packs': []})
    tracked, assets, excluded = [], [], collections.Counter()
    inode_hashes = {}
    def walk_error(error):
        raise error
    for top in ['outputs','work']:
        if not (ROOT / top).exists():
            continue
        for base, dirs, files in os.walk(ROOT / top, onerror=walk_error):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith('tmp'))
            for directory in dirs:
                if (Path(base) / directory).is_symlink():
                    raise ValueError(f'Symbolic links cannot be inventoried: {Path(base) / directory}')
            for name in sorted(files):
                p = Path(base) / name
                if p.is_symlink():
                    raise ValueError(f'Symbolic links cannot be inventoried: {p}')
                rel = p.relative_to(ROOT).as_posix()
                ext = p.suffix.lower()
                if top == 'work' and '/publication/' in rel:
                    continue
                stat = p.stat()
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
                inode_key = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
                digest = inode_hashes.get(inode_key)
                if digest is None:
                    digest = sha(p)
                    inode_hashes[inode_key] = digest
                assets.append({'path':rel, 'bytes':stat.st_size, 'sha256':digest})
    # Preserve the final verification receipts even when their location is a cache.
    for p in (ROOT/'work/element-motion/sigil-02-active-elements').rglob('*audit.json'):
        fetch_assets.safe_target(p.relative_to(ROOT).as_posix(), ROOT)
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
    out = fetch_assets.safe_target('work/publication/assets.json', ROOT).parent
    out.mkdir(parents=True, exist_ok=True)
    manifest = {'version':1, 'repository':repository, 'tag':tag,
                'assets':assets, 'packs':[{k:v for k,v in p.items() if k!='files'} for p in packs]}
    fetch_assets.validate_manifest(manifest)
    fetch_assets.safe_target('work/publication/assets.json', ROOT).write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    plan = {'tracked':tracked, 'packs':packs, 'excludedCategories':dict(excluded)}
    fetch_assets.safe_target('work/publication/plan.json', ROOT).write_text(json.dumps(plan, indent=2)+'\n', encoding='utf-8')
    stats = {'gitFiles':len(tracked), 'gitMiB':round(sum((ROOT/p).stat().st_size for p in tracked)/1024**2,1),
             'releasePaths':len(assets),'uniqueAssets':len(unique),'packs':len(packs),
             'releaseMiB':round(sum(a['bytes'] for a in unique.values())/1024**2,1),
             'excludedCategories':dict(excluded)}
    fetch_assets.safe_target('work/publication/publication-scope.json', ROOT).write_text(json.dumps(stats, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(stats, indent=2))
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True, help='New draft-release tag, e.g. v0.2.0')
    parser.add_argument('--repository', default='cybrdelic/cybr-elements', help='owner/repository for the release')
    args = parser.parse_args(argv)
    try:
        prepare(args.tag, args.repository)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f'Publication inventory failed: {error}\n')

if __name__ == '__main__':
    main()
