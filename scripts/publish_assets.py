"""Upload a complete staged inventory to its existing GitHub draft release.

Run prepare_publication.py --tag NEW_TAG first and create that draft using gh.
The repository and tag come from work/publication/assets.json. Published
releases are immutable. ZIPs are deterministic, bounded to one pack at a time,
and retained after a failed upload. No asset is silently replaced remotely.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import urllib.parse
import zipfile
import fetch_assets

ROOT = Path(__file__).resolve().parents[1]


def gh(*args):
    process = subprocess.run(['gh', *args], capture_output=True, text=True)
    if process.returncode:
        raise RuntimeError(process.stderr[-2000:] or 'gh command failed')
    return process.stdout


def write_json(path, value):
    """Persist upload progress atomically, including when a process is stopped."""
    descriptor, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
        Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def remote_assets(repository, release_id):
    pages = json.loads(gh('api', f'repos/{repository}/releases/{release_id}/assets?per_page=100', '--paginate', '--slurp'))
    names = [asset['name'] for page in pages for asset in page]
    if len(names) != len(set(names)):
        raise RuntimeError('Release contains duplicate asset names')
    return {asset['name']: asset for page in pages for asset in page}


def validate_plan(manifest, plan):
    fetch_assets.validate_manifest(manifest)
    if not isinstance(plan, dict) or not isinstance(plan.get('packs'), list):
        raise ValueError('Publication plan must contain a pack list')
    if any(not isinstance(pack, dict) or not isinstance(pack.get('name'), str) for pack in plan['packs']):
        raise ValueError('Invalid publication pack record')
    metadata = {pack['name']: pack for pack in manifest['packs']}
    planned_names = [pack.get('name') for pack in plan['packs']]
    if len(planned_names) != len(set(planned_names)) or set(planned_names) != set(metadata):
        raise ValueError('Manifest and publication plan packs differ')
    expected = {}
    for asset in manifest['assets']:
        expected[(asset['pack'], asset['member'])] = (asset['bytes'], asset['sha256'])
    planned = {}
    for pack in plan['packs']:
        name = pack['name']
        if not isinstance(pack.get('files'), list):
            raise ValueError(f'Invalid file list: {name}')
        size = 0
        for asset in pack['files']:
            if not isinstance(asset, dict):
                raise ValueError(f'Invalid publication source: {name}')
            source = asset.get('path')
            fetch_assets.relative_path(source)
            key = (name, source)
            signature = (asset.get('bytes'), asset.get('sha256'))
            if key in planned or expected.get(key) != signature:
                raise ValueError(f'Plan source differs from manifest: {source}')
            planned[key] = signature
            size += asset['bytes']
        if size != pack.get('uncompressedBytes') or size != metadata[name]['uncompressedBytes']:
            raise ValueError(f'Plan size differs from manifest: {name}')
    if planned != expected:
        raise ValueError('Publication plan omits manifest members')


def build_pack(pack, target):
    """Use canonical ZIP metadata so a restored checkout produces the same ZIP."""
    sources = []
    for asset in sorted(pack['files'], key=lambda item: item['path']):
        source = fetch_assets.safe_target(asset['path'], ROOT)
        if not source.is_file() or source.stat().st_size != asset['bytes'] or fetch_assets.digest(source) != asset['sha256']:
            raise RuntimeError(f'Source changed: {asset["path"]}')
        sources.append((asset, source))
    descriptor, temporary = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.partial', dir=target.parent)
    os.close(descriptor)
    temporary = Path(temporary)
    try:
        with zipfile.ZipFile(temporary, 'w', allowZip64=True) as bundle:
            for asset, source in sources:
                info = zipfile.ZipInfo(asset['path'], date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_STORED
                with source.open('rb') as stream, bundle.open(info, 'w', force_zip64=True) as destination:
                    fetch_assets.copy_bounded(stream, destination, asset['bytes'], asset['path'])
        # Check the archived bytes too; a source may change between hashing and
        # copying, especially during a long render or solver run.
        with zipfile.ZipFile(temporary) as bundle:
            for asset, _ in sources:
                with bundle.open(asset['path']) as stream:
                    actual = hashlib.file_digest(stream, 'sha256').hexdigest()
                if actual != asset['sha256']:
                    raise RuntimeError(f'Source changed while archiving: {asset["path"]}')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def publish():
    directory = fetch_assets.safe_target('work/publication/assets.json', ROOT).parent
    manifest_path = fetch_assets.safe_target('work/publication/assets.json', ROOT)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    plan = json.loads(fetch_assets.safe_target('work/publication/plan.json', ROOT).read_text(encoding='utf-8'))
    validate_plan(manifest, plan)
    scope_path = fetch_assets.safe_target('work/publication/publication-scope.json', ROOT)
    scope = json.loads(scope_path.read_text(encoding='utf-8')) if scope_path.exists() else None
    receipt_path = fetch_assets.safe_target('docs/release-verification.json', ROOT)
    published_scope_path = fetch_assets.safe_target('docs/publication-scope.json', ROOT)
    repository, tag = manifest['repository'], manifest['tag']
    previous_path = fetch_assets.safe_target('docs/assets.json', ROOT)
    if previous_path.exists():
        previous = json.loads(previous_path.read_text(encoding='utf-8'))
        if previous.get('tag') == tag and any('sha256' in pack for pack in previous.get('packs', [])):
            raise RuntimeError('The recorded release is immutable; prepare a new release tag.')
    # Query by tag directly; a list limited to its first page can miss old drafts.
    release = json.loads(gh('api', f'repos/{repository}/releases/tags/{urllib.parse.quote(tag, safe="")}'))
    if release.get('tag_name') != tag or release.get('draft') is not True:
        raise RuntimeError(f'Release {tag} must exist and be a draft before uploading.')
    existing = remote_assets(repository, release['id'])
    metadata = {pack['name']: pack for pack in manifest['packs']}
    for number, pack in enumerate(plan['packs'], 1):
        name = pack['name']
        info = metadata[name]
        target = fetch_assets.safe_target(f'work/publication/{name}', ROOT)
        remote = existing.get(name)
        if remote and info.get('sha256'):
            if remote['size'] != info['bytes'] or remote.get('digest') != 'sha256:' + info['sha256']:
                raise RuntimeError(f'Existing remote pack differs: {name}')
            if target.exists() and fetch_assets.digest(target) == info['sha256']:
                target.unlink()
            print(f'[{number}/{len(plan["packs"])}] verified existing {name}', flush=True)
            continue
        # One pack at a time: concurrent free-space checks can all pass and then
        # collectively exhaust the disk. Leave room for the ZIP member headers.
        required = pack['uncompressedBytes'] + 64*1024**2
        if shutil.disk_usage(ROOT).free < required:
            raise RuntimeError(f'Insufficient free space for {name}: need {required/1024**2:.0f} MiB')
        if target.exists():
            if not info.get('sha256') or target.stat().st_size != info['bytes'] or fetch_assets.digest(target) != info['sha256']:
                raise RuntimeError(f'Unrecognized local archive; preserve or move it first: {target}')
        else:
            build_pack(pack, target)
        info.update(bytes=target.stat().st_size, sha256=fetch_assets.digest(target))
        write_json(manifest_path, manifest)
        if remote:
            if remote['size'] != info['bytes'] or remote.get('digest') != 'sha256:' + info['sha256']:
                raise RuntimeError(f'Existing remote pack differs: {name}')
        else:
            # No clobber. '--' prevents a tag from becoming a CLI option.
            gh('release', 'upload', '--repo', repository, '--', tag, str(target))
            uploaded = remote_assets(repository, release['id']).get(name)
            if not uploaded or uploaded['size'] != info['bytes'] or uploaded.get('digest') != 'sha256:' + info['sha256']:
                raise RuntimeError(f'Remote upload verification failed: {name}')
        target.unlink()
        print(f'[{number}/{len(plan["packs"])}] SHA-256 verified {name} ({info["bytes"]/1024**2:.1f} MiB)', flush=True)
    fetch_assets.validate_manifest(manifest, require_archive_integrity=True)
    # Re-fetch every remote record before promoting local documentation. A failed
    # or partial publication leaves the last release inventory fully intact.
    final = remote_assets(repository, release['id'])
    for info in manifest['packs']:
        remote = final.get(info['name'])
        if not remote or remote['size'] != info['bytes'] or remote.get('digest') != 'sha256:' + info['sha256']:
            raise RuntimeError(f'Final release verification failed: {info["name"]}')
    receipts = {'repository': repository, 'release': tag, 'verifiedPacks': len(manifest['packs']),
                'bytes': sum(pack['bytes'] for pack in manifest['packs']),
                'verification': 'GitHub asset digest and size match local SHA-256 for every ZIP'}
    previous_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(previous_path, manifest)
    write_json(receipt_path, receipts)
    if scope is not None:
        write_json(published_scope_path, scope)
    print(json.dumps(receipts), flush=True)
    return receipts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        publish()
    except (OSError, ValueError, RuntimeError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, f'Asset publication failed: {error}\n')


if __name__ == '__main__':
    main()
