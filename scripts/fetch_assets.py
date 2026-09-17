"""Restore optional release assets to their original paths, verifying SHA-256.

Current 02 movies, fonts and UI are already in Git. Use --site for the complete
historical gallery or --all for the gallery and research inputs. No packages
outside Python's standard library are required.
"""
from pathlib import Path, PurePosixPath
import argparse
import collections
import hashlib
import json
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def safe_target(rel):
    p = PurePosixPath(rel)
    if p.is_absolute() or '..' in p.parts or '\\' in rel or ':' in rel:
        raise ValueError(f'Unsafe asset path: {rel}')
    target = (ROOT / rel).resolve()
    if not target.is_relative_to(ROOT):
        raise ValueError(f'Asset escapes checkout: {rel}')
    return target

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--site', action='store_true')
    scope.add_argument('--all', action='store_true')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'docs/assets.json').read_text())
    assets = [a for a in manifest['assets'] if args.all or a['path'].startswith('outputs/')]
    groups = collections.defaultdict(list)
    verified = 0
    for asset in assets:
        target = safe_target(asset['path'])
        if target.exists():
            if target.stat().st_size != asset['bytes'] or digest(target) != asset['sha256']:
                raise SystemExit(f'Existing file differs; preserve or move it before restoring: {asset["path"]}')
            verified += 1
        else:
            groups[asset['pack']].append(asset)
    missing = sum(map(len, groups.values()))
    if args.verify_only:
        print(f'{verified} verified; {missing} missing.')
        raise SystemExit(1 if missing else 0)
    temp = ROOT / '.asset-downloads'
    temp.mkdir(exist_ok=True)
    packs = {p['name']:p for p in manifest['packs']}
    base = f'https://github.com/{manifest["repository"]}/releases/download/{manifest["tag"]}'
    for number, (name, wanted) in enumerate(groups.items(), 1):
        archive = temp / name
        info = packs[name]
        required = info.get('bytes', info['uncompressedBytes']) + sum(a['bytes'] for a in wanted)
        if shutil.disk_usage(ROOT).free < required + 32*1024**2:
            raise SystemExit(f'Need at least {required/1024**2:.0f} MiB free for {name}.')
        print(f'[{number}/{len(groups)}] {name}: restoring {len(wanted)} files', flush=True)
        try:
            request = urllib.request.Request(f'{base}/{name}', headers={'User-Agent':'cybr-elements-assets/1'})
            with urllib.request.urlopen(request, timeout=120) as response, archive.open('wb') as f:
                shutil.copyfileobj(response, f, 1024**2)
            if 'sha256' in info and digest(archive) != info['sha256']:
                raise RuntimeError(f'Archive checksum mismatch: {name}')
            with zipfile.ZipFile(archive) as z:
                for asset in wanted:
                    target = safe_target(asset['path'])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    partial = target.with_name(target.name + '.download-partial')
                    if partial.exists():
                        raise RuntimeError(f'Partial file already exists: {partial}')
                    try:
                        with z.open(asset['member']) as src, partial.open('xb') as dst:
                            shutil.copyfileobj(src, dst, 1024**2)
                        if partial.stat().st_size != asset['bytes'] or digest(partial) != asset['sha256']:
                            raise RuntimeError(f'Asset checksum mismatch: {asset["path"]}')
                        partial.replace(target)
                        verified += 1
                    finally:
                        partial.unlink(missing_ok=True)
        finally:
            archive.unlink(missing_ok=True)
    print(f'{verified} assets verified. Ready to serve the site.')

if __name__ == '__main__':
    main()
