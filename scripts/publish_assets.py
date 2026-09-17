"""Maintainer utility: upload inventoried packs to the named draft release.

Requires authenticated gh. Writes only temporary ZIPs, the asset manifest and
upload receipts. Deletes each generated ZIP after a verified remote upload.
The source files are never deleted. Run prepare_publication.py first.
"""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TEMP = ROOT / 'work/publication'
REPO = 'cybrdelic/cybr-elements'
TAG = 'v0.1.0'

def gh(*args):
    p = subprocess.run(['gh', *args], capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr[-2000:])
    return p.stdout

def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def remote_assets(release_id):
    pages = json.loads(gh('api', f'repos/{REPO}/releases/{release_id}/assets?per_page=100', '--paginate', '--slurp'))
    return {a['name']:a for page in pages for a in page}

def main():
    manifest_path = ROOT / 'docs/assets.json'
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads((TEMP / 'plan.json').read_text())
    releases = json.loads(gh('api', f'repos/{REPO}/releases?per_page=100'))
    release = next(r for r in releases if r['tag_name'] == TAG)
    existing = remote_assets(release['id'])
    metadata = {p['name']:p for p in manifest['packs']}
    lock = threading.Lock()
    def upload(item):
        number, pack = item
        name = pack['name']
        info = metadata[name]
        target = (TEMP / name).resolve()
        assert target.is_relative_to(TEMP.resolve())
        if name in existing and info.get('sha256'):
            a = existing[name]
            if a['size'] == info['bytes'] and a.get('digest') == 'sha256:'+info['sha256']:
                if target.exists() and digest(target) == info['sha256']:
                    target.unlink()
                print(f'[{number}/{len(plan["packs"])}] verified existing {name}', flush=True)
                return
            raise RuntimeError(f'Existing remote pack differs: {name}')
        if shutil.disk_usage(ROOT).free < pack['uncompressedBytes'] + 64*1024**2:
            raise RuntimeError('Insufficient free space for the next temporary archive')
        with zipfile.ZipFile(target, 'w', allowZip64=True) as z:
            for asset in pack['files']:
                source = (ROOT / asset['path']).resolve()
                assert source.is_relative_to(ROOT)
                if source.stat().st_size != asset['bytes'] or digest(source) != asset['sha256']:
                    raise RuntimeError(f'Source changed: {asset["path"]}')
                z.write(source, asset['path'], compress_type=zipfile.ZIP_STORED)
        with lock:
            info.update(bytes=target.stat().st_size, sha256=digest(target))
            manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
        # No clobber: never replace remote assets silently.
        gh('release', 'upload', TAG, str(target), '--repo', REPO)
        uploaded = remote_assets(release['id'])[name]
        if uploaded['size'] != info['bytes'] or uploaded.get('digest') != 'sha256:'+info['sha256']:
            raise RuntimeError(f'Remote upload verification failed: {name}')
        target.unlink()
        print(f'[{number}/{len(plan["packs"])}] uploaded + SHA-256 verified {name} ({info["bytes"]/1024**2:.1f} MiB)', flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(upload, enumerate(plan['packs'], 1)))
    receipts = {'repository':REPO, 'release':TAG, 'verifiedPacks':len(manifest['packs']),
                'bytes':sum(p['bytes'] for p in manifest['packs']),
                'verification':'GitHub asset digest and size match local SHA-256 for every ZIP'}
    (ROOT/'docs/release-verification.json').write_text(json.dumps(receipts, indent=2)+'\n')
    print(json.dumps(receipts), flush=True)

if __name__ == '__main__':
    main()
