"""Restore only required assets, into an isolated workspace, never the checkout."""
from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

from adapter import sha256


def safe_path(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if not relative or path.is_absolute() or '..' in path.parts or '\\' in relative or ':' in relative:
        raise ValueError(f'Unsafe relative path: {relative!r}')
    root = root.resolve()
    target = root.joinpath(*path.parts)
    if not target.resolve().is_relative_to(root):
        raise ValueError(f'Path escapes workspace: {relative}')
    return target


def verify(path: Path, record: dict[str, Any]) -> None:
    if path.stat().st_size != record['bytes'] or sha256(path) != record['sha256']:
        raise ValueError(f'Asset checksum mismatch: {path}')


def copy_new(source: Path, target: Path) -> None:
    if target.exists() or target.is_symlink():
        raise FileExistsError(f'Refusing to replace {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    # A real copy, never a hard link: drivers are allowed to consume workspace caches.
    with source.open('rb') as src, target.open('xb') as dst:
        shutil.copyfileobj(src, dst, 1024 * 1024)


def restore(root: Path, workspace: Path, required: list[str], *,
            input_cache: Path | None = None, download: bool = False) -> list[dict[str, Any]]:
    manifest_path = root / 'docs/assets.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.is_file() else {}
    records = {item['path']: item for item in manifest.get('assets', [])}
    packs = {item['name']: item for item in manifest.get('packs', [])}
    pending: dict[str, list[dict[str, Any]]] = defaultdict(list)
    receipts = []
    candidates = [root] + ([input_cache] if input_cache else [])
    for relative in sorted(set(required)):
        target = safe_path(workspace, relative)
        record = records.get(relative)
        source = next((safe_path(base, relative) for base in candidates
                       if safe_path(base, relative).is_file()), None)
        if source is not None:
            if record:
                verify(source, record)
            elif input_cache and source.is_relative_to(input_cache.resolve()):
                raise ValueError(f'External cached input lacks an asset-manifest checksum: {relative}')
            copy_new(source, target)
            receipts.append({'path': relative, 'sha256': sha256(target), 'bytes': target.stat().st_size,
                             'origin': 'checkout' if source.is_relative_to(root) else 'verified-input-cache'})
        elif download and record:
            pending[record['pack']].append(record)
        else:
            instruction = 'Use --restore-inputs to retrieve it into the new workspace.' if record else 'Input is not in the published asset manifest.'
            raise FileNotFoundError(f'Missing required input: {relative}. {instruction}')
    for name, wanted in pending.items():
        if name not in packs:
            raise ValueError(f'Missing pack metadata: {name}')
        info = packs[name]
        archive = safe_path(workspace / '.downloads', name)
        archive.parent.mkdir(parents=True, exist_ok=True)
        required_bytes = info.get('bytes', info.get('uncompressedBytes', 0)) + sum(a['bytes'] for a in wanted)
        if shutil.disk_usage(workspace).free < required_bytes + 128 * 1024**2:
            raise OSError(f'Insufficient space to restore {name}')
        url = f'https://github.com/{manifest["repository"]}/releases/download/{manifest["tag"]}/{name}'
        print(f'Restoring {len(wanted)} required inputs from {name}', flush=True)
        request = urllib.request.Request(url, headers={'User-Agent': 'cybr-elements-cpu/1'})
        try:
            with urllib.request.urlopen(request, timeout=120) as response, archive.open('xb') as dst:
                shutil.copyfileobj(response, dst, 1024 * 1024)
            if 'sha256' in info and sha256(archive) != info['sha256']:
                raise ValueError(f'Archive checksum mismatch: {name}')
            with zipfile.ZipFile(archive) as package:
                for record in wanted:
                    relative = record['path']
                    target = safe_path(workspace, relative)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    partial = target.with_suffix(target.suffix + '.partial')
                    # Extract the named entry only; never extractall or follow zip paths.
                    with package.open(record['member']) as src, partial.open('xb') as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
                    verify(partial, record)
                    if target.exists():
                        raise FileExistsError(target)
                    partial.rename(target)
                    receipts.append({'path': relative, 'sha256': record['sha256'], 'bytes': record['bytes'],
                                     'origin': 'verified-release-asset', 'pack': name})
        finally:
            archive.unlink(missing_ok=True)
    return receipts
