"""Restore optional release assets to their original paths, verifying SHA-256.

Current films, fonts and UI are already in Git. Use --site for the complete
historical gallery or --all for the gallery and research inputs. Python 3.11+
and its standard library are sufficient; local edits are never overwritten.
"""
from pathlib import Path, PurePosixPath
import argparse
import collections
import errno
import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CHUNK_BYTES = 1024**2


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def relative_path(value):
    """Accept only canonical file paths, including on Windows checkouts."""
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        raise ValueError(f'Unsafe asset path: {value!r}')
    path = PurePosixPath(value)
    if (path.is_absolute() or any(part in {'', '.', '..'} for part in value.split('/'))
            or '\\' in value or ':' in value):
        raise ValueError(f'Unsafe asset path: {value}')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
    if any(re.search(r'[<>"|?*]', part) or part.endswith(('.', ' '))
           or part.split('.')[0].upper() in reserved for part in path.parts):
        raise ValueError(f'Asset path is not portable to Windows: {value}')
    return path


def safe_target(rel, root=None):
    relative_path(rel)
    root = (ROOT if root is None else Path(root)).resolve()
    target = root / rel
    # Reject symlinks even when they currently point back inside the checkout.
    # Otherwise restoration can replace a different file or trust a broken link.
    current = root
    for part in PurePosixPath(rel).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f'Asset path contains a symbolic link: {rel}')
    if not target.resolve().is_relative_to(root):
        raise ValueError(f'Asset escapes checkout: {rel}')
    return target


def validate_manifest(manifest, *, require_archive_integrity=False):
    """Validate before touching files or constructing download URLs."""
    if not isinstance(manifest, dict) or manifest.get('version', 1) != 1:
        raise ValueError('Unsupported asset manifest version')
    repository = manifest.get('repository')
    if (not isinstance(repository, str)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+', repository)
            or repository.split('/')[-1] in {'.', '..'}):
        raise ValueError('Invalid asset repository')
    tag = manifest.get('tag')
    if not isinstance(tag, str) or not tag or any(ord(c) < 32 for c in tag):
        raise ValueError('Invalid release tag')
    assets, packs = manifest.get('assets'), manifest.get('packs')
    if not isinstance(assets, list) or not isinstance(packs, list):
        raise ValueError('Manifest must contain asset and pack lists')

    def size(value, label):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f'Invalid byte count: {label}')

    def checksum(value, label):
        if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ValueError(f'Invalid SHA-256: {label}')

    names = set()
    for pack in packs:
        if not isinstance(pack, dict):
            raise ValueError('Invalid pack record')
        name = pack.get('name')
        relative_path(name)
        if '/' in name or not name.endswith('.zip') or name in names:
            raise ValueError(f'Unsafe or duplicate pack name: {name}')
        names.add(name)
        size(pack.get('uncompressedBytes'), name)
        if ('bytes' in pack) != ('sha256' in pack):
            raise ValueError(f'Incomplete archive integrity metadata: {name}')
        if require_archive_integrity or 'bytes' in pack:
            size(pack.get('bytes'), name)
        if require_archive_integrity or 'sha256' in pack:
            checksum(pack.get('sha256'), name)
    paths, members = set(), {}
    for asset in assets:
        if not isinstance(asset, dict):
            raise ValueError('Invalid asset record')
        path = asset.get('path')
        relative_path(path)
        relative_path(asset.get('member'))
        if path in paths:
            raise ValueError(f'Duplicate asset path: {path}')
        paths.add(path)
        size(asset.get('bytes'), path)
        checksum(asset.get('sha256'), path)
        pack = asset.get('pack')
        if not isinstance(pack, str) or pack not in names:
            raise ValueError(f'Unknown pack for asset: {path}')
        key = (pack, asset['member'])
        signature = (asset['bytes'], asset['sha256'])
        if key in members and members[key] != signature:
            raise ValueError(f'Conflicting archive member: {asset["member"]}')
        members[key] = signature
    return manifest


def copy_bounded(source, destination, expected, label):
    """Do not let a corrupt ZIP or HTTP response exceed its declared size."""
    total = 0
    while True:
        chunk = source.read(min(CHUNK_BYTES, expected - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > expected:
            raise RuntimeError(f'Byte count exceeds manifest: {label}')
        destination.write(chunk)
    if total != expected:
        raise RuntimeError(f'Byte count mismatch: {label}')


def install_verified(partial, target, expected):
    """Install without replacing local files, including on filesystems without links."""
    try:
        os.link(partial, target)
    except OSError as error:
        if error.errno not in {errno.ENOSYS, errno.EOPNOTSUPP, errno.EPERM, errno.EXDEV}:
            raise
        # FAT/exFAT and some network filesystems do not support hard links.
        # Exclusive creation still preserves a concurrent local file; a failed
        # copy removes only the destination owned by this invocation.
        with target.open('xb') as destination:
            try:
                with partial.open('rb') as source:
                    copy_bounded(source, destination, expected, str(target))
            except BaseException:
                destination.close()
                target.unlink(missing_ok=True)
                raise


def restore_assets(manifest, *, all_assets=False, verify_only=False):
    validate_manifest(manifest, require_archive_integrity=True)
    assets = [a for a in manifest['assets'] if all_assets or a['path'].startswith('outputs/')]
    groups = collections.defaultdict(list)
    verified = 0
    for asset in assets:
        target = safe_target(asset['path'])
        if target.exists():
            if not target.is_file() or target.stat().st_size != asset['bytes'] or digest(target) != asset['sha256']:
                raise RuntimeError(f'Existing file differs; preserve or move it before restoring: {asset["path"]}')
            verified += 1
        else:
            groups[asset['pack']].append(asset)
    missing = sum(map(len, groups.values()))
    if verify_only:
        print(f'{verified} verified; {missing} missing.')
        return 1 if missing else 0
    if not groups:
        print(f'{verified} assets verified. Ready to serve the site.')
        return 0
    # A private temporary directory avoids shared filenames, stale downloads,
    # and following a caller-controlled .asset-downloads symlink.
    packs = {p['name']: p for p in manifest['packs']}
    tag = urllib.parse.quote(manifest['tag'], safe='')
    base = f'https://github.com/{manifest["repository"]}/releases/download/{tag}'
    with tempfile.TemporaryDirectory(prefix='cybr-assets-', dir=ROOT) as temporary:
        for number, (name, wanted) in enumerate(groups.items(), 1):
            archive = Path(temporary) / name
            info = packs[name]
            required = info['bytes'] + sum(a['bytes'] for a in wanted)
            if shutil.disk_usage(ROOT).free < required + 32*1024**2:
                raise RuntimeError(f'Need at least {(required + 32*1024**2)/1024**2:.0f} MiB free for {name}.')
            print(f'[{number}/{len(groups)}] {name}: restoring {len(wanted)} files', flush=True)
            try:
                request = urllib.request.Request(f'{base}/{urllib.parse.quote(name)}', headers={'User-Agent': 'cybr-elements-assets/2'})
                with urllib.request.urlopen(request, timeout=120) as response, archive.open('xb') as stream:
                    copy_bounded(response, stream, info['bytes'], name)
                if digest(archive) != info['sha256']:
                    raise RuntimeError(f'Archive checksum mismatch: {name}')
                with zipfile.ZipFile(archive) as bundle:
                    entries = bundle.infolist()
                    if len({entry.filename for entry in entries}) != len(entries):
                        raise RuntimeError(f'Duplicate archive member: {name}')
                    for asset in wanted:
                        entry = bundle.getinfo(asset['member'])
                        if entry.is_dir() or entry.file_size != asset['bytes'] or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                            raise RuntimeError(f'Invalid archive member: {asset["member"]}')
                        target = safe_target(asset['path'])
                        target.parent.mkdir(parents=True, exist_ok=True)
                        # Create a unique file in the destination filesystem so
                        # verified installation can be atomic without overwrites.
                        descriptor, partial_name = tempfile.mkstemp(prefix='.cybr-asset-', suffix='.partial', dir=target.parent)
                        partial = Path(partial_name)
                        try:
                            with os.fdopen(descriptor, 'wb') as destination, bundle.open(entry) as source:
                                copy_bounded(source, destination, asset['bytes'], asset['path'])
                            if digest(partial) != asset['sha256']:
                                raise RuntimeError(f'Asset checksum mismatch: {asset["path"]}')
                            safe_target(asset['path'])
                            partial.chmod(0o644)
                            # Hard linking refuses any file created during the
                            # download instead of silently replacing a local edit.
                            try:
                                install_verified(partial, target, asset['bytes'])
                            except FileExistsError:
                                if not target.is_file() or target.stat().st_size != asset['bytes'] or digest(target) != asset['sha256']:
                                    raise RuntimeError(f'Asset appeared during restore; preserved: {asset["path"]}')
                            verified += 1
                        finally:
                            partial.unlink(missing_ok=True)
            finally:
                archive.unlink(missing_ok=True)
    print(f'{verified} assets verified. Ready to serve the site.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--site', action='store_true')
    scope.add_argument('--all', action='store_true')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args(argv)
    try:
        manifest = json.loads((ROOT / 'docs/assets.json').read_text(encoding='utf-8'))
        code = restore_assets(manifest, all_assets=args.all, verify_only=args.verify_only)
    except (OSError, ValueError, RuntimeError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, f'Asset restore failed: {error}\n')
    if code:
        raise SystemExit(code)


if __name__ == '__main__':
    main()
