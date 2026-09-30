#!/usr/bin/env python3
"""Solve the complete production water trajectory and render selected frame IDs.

Each shard computes fresh, identical 240-frame physical caches before rendering
its selection. Cache hashes cover decoded physical payloads, so archive creation
times do not prevent comparison between independently produced shards.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import operator
from pathlib import Path
import shutil
import sys
import time

from rerender_batch import BASE, ROOT, checked, retained_inputs

FRAME_COUNT = 240
PARCEL_COUNT = 138_022
GRID = (264, 106, 168)


def _selected_frames(frames):
    selected = []
    try:
        for value in frames:
            if isinstance(value, bool):
                raise TypeError('boolean frame ID')
            selected.append(operator.index(value))
    except TypeError as error:
        raise ValueError('Selected frame IDs must be integers') from error
    if not selected or any(frame < 0 or frame >= FRAME_COUNT for frame in selected):
        raise ValueError('Selected frames must lie inside 0..239')
    if len(selected) != len(set(selected)):
        raise ValueError('Selected frames must be unique')
    return selected


def _file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _gzip_hash(path):
    digest = hashlib.sha256()
    with gzip.open(path, 'rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _velocity_hash(path):
    import numpy as np

    digest = hashlib.sha256()
    with np.load(path, allow_pickle=False) as vectors:
        if set(vectors.files) != {'surface', 'drops', 'drop_positions'}:
            raise RuntimeError(f'Unexpected velocity cache fields: {path}')
        for name in sorted(vectors.files):
            array = vectors[name]
            if array.dtype.kind != 'f' or array.ndim != 2 or array.shape[1] != 3:
                raise RuntimeError(f'Invalid velocity cache array {name}: {path}')
            if not np.isfinite(array).all():
                raise RuntimeError(f'Nonfinite velocity cache array {name}: {path}')
            array = np.ascontiguousarray(array, dtype=array.dtype.newbyteorder('<'))
            header = json.dumps([name, array.dtype.str, list(array.shape)],
                                separators=(',', ':')).encode('ascii')
            digest.update(len(header).to_bytes(4, 'little'))
            digest.update(header)
            if array.size:
                digest.update(memoryview(array).cast('B'))
    return digest.hexdigest()


def cache_hashes(output_root):
    """Hash all 240 physical particle, mesh and canonical velocity payloads."""
    output = Path(output_root).resolve()
    config = json.loads((output / 'config.json').read_text())
    physical_config = {key: value for key, value in config.items()
                       if key not in ('forceRoot', 'sourceRoot')}
    config_hash = hashlib.sha256(json.dumps(physical_config, sort_keys=True,
                                            separators=(',', ':')).encode()).hexdigest()
    frames = {}
    for frame in range(FRAME_COUNT):
        name = f'{frame:04d}'
        frames[name] = {
            'particles': _gzip_hash(output / 'particles' / f'{name}.gz'),
            'mesh': _gzip_hash(output / 'mesh' / f'{name}.mesh.gz'),
            'velocity': _velocity_hash(output / 'mesh' / f'{name}.velocity.npz'),
        }
    payload = {'configSha256': config_hash, 'frames': frames}
    aggregate = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                         separators=(',', ':')).encode()).hexdigest()
    return {
        'algorithm': 'sha256',
        'encoding': 'decoded-gzip-binary-and-canonical-little-endian-npz-arrays-v1',
        'configSha256': config_hash,
        'frames': frames,
        'sha256': aggregate,
    }


def _verified_inputs(input_root):
    wanted = retained_inputs('water')
    inventory = json.loads((ROOT / 'docs/assets.json').read_text())
    assets = {asset['path']: asset for asset in inventory['assets'] if asset['path'] in wanted}
    if set(assets) != wanted:
        raise RuntimeError('Published inventory is missing retained water inputs')
    verified = {}
    for relative in sorted(wanted):
        path = input_root / relative
        if not path.is_file():
            raise FileNotFoundError(f'Missing restored water input: {path}')
        actual = _file_hash(path)
        if actual != assets[relative]['sha256']:
            raise RuntimeError(f'Restored water input failed SHA-256 verification: {path}')
        verified[relative] = actual
    return verified


def render_water_slice(input_root, output_root, frames, threads, blender, python_executable):
    """Return absolute framesDirectory, reports and deterministic cacheHashes.

    input_root contains the restored repository-shaped retained input paths.
    output_root is a fresh directory for this water shard, including all caches.
    Frame IDs are zero-based and remain unchanged in the selected JPG filenames.
    """
    selected = _selected_frames(frames)
    if isinstance(threads, bool):
        raise ValueError('threads must be an integer between 1 and 64')
    try:
        threads = operator.index(threads)
    except TypeError as error:
        raise ValueError('threads must be an integer between 1 and 64') from error
    if not 1 <= threads <= 64:
        raise ValueError('threads must be between 1 and 64')
    input_root = Path(input_root).resolve()
    output = Path(output_root).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise RuntimeError('Water slice output exists; select a fresh output directory')
    inputs = _verified_inputs(input_root)
    source = ROOT / BASE
    ground = input_root / BASE / 'sigil-02-bending-ground/full'
    config = json.loads((source / 'sigil-02-active-elements/water-full/config.json').read_text())
    if (config.get('frames') != FRAME_COUNT
            or tuple(config.get(key) for key in ('nx', 'ny', 'nz')) != GRID
            or (ground / 'parcels.f32').stat().st_size != PARCEL_COUNT * 9 * 4):
        raise RuntimeError('Water slice requires the full 138022-parcel, 264x106x168, 240-frame preset')
    config.update(forceRoot=str(ground), sourceRoot=str(ground))
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    (output / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    for name in ('parcels.f32', 'guides.npz'):
        shutil.copy2(ground / name, output / name)
    checked(['node', source / 'sigil_02_active_water.mjs', '--full', '--offline',
             '--output', output, '--force-root', ground], output / 'solve.log')
    checked([python_executable, source / 'sigil_02_active_mesh.py', '--full', '--offline',
             '--output', output], output / 'mesh.log')
    hashes = cache_hashes(output)
    hash_report = output / 'cache-hashes.json'
    hash_report.write_text(json.dumps(hashes, indent=2) + '\n')
    frames_directory = output / 'frames'
    checked([blender, '--background', '--python', source / 'sigil_02_active_water_render.py', '--',
             '--full', '--output', output, '--render-output', frames_directory,
             '--width', 1280, '--height', 720, '--samples', 24, '--threads', threads,
             '--device', 'cpu', '--frames', ','.join(map(str, selected)), '--keep-cache'],
            output / 'render.log')
    expected = {f'{frame:04d}.jpg' for frame in selected}
    if ({path.name for path in frames_directory.glob('*.jpg')} != expected
            or any((frames_directory / name).stat().st_size == 0 for name in expected)):
        raise RuntimeError('Water renderer did not produce exactly the selected frame IDs')
    source_paths = [source / name for name in ('sigil_02_active_water.mjs',
                    'sigil_02_active_mesh.py', 'sigil_02_active_water_render.py', 'bending_surface.py')]
    source_paths.append(Path(__file__).resolve())
    report = output / 'slice-report.json'
    report.write_text(json.dumps({
        'complete': True, 'element': 'water', 'freshFrames': True, 'oldFilmPixelsUsed': False,
        'elapsedSeconds': time.monotonic() - started, 'nativeResolution': [1280, 720],
        'samples': 24, 'threads': threads, 'fps': 30, 'simulatedFrames': FRAME_COUNT,
        'selectedFrames': selected, 'parcels': PARCEL_COUNT, 'grid': list(GRID),
        'inputSha256': inputs, 'cacheSha256': hashes['sha256'],
        'sourceSha256': {str(path.relative_to(ROOT)): _file_hash(path) for path in source_paths},
    }, indent=2) + '\n')
    reports = [output / 'config.json', output / 'particles/manifest.json',
               output / 'mesh/manifest.json', hash_report, report]
    return {'framesDirectory': str(frames_directory),
            'reports': [str(path) for path in reports], 'cacheHashes': hashes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--frames', type=int, nargs='+', required=True,
                        help='Unique final frame IDs in 0..239; filenames retain these IDs')
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--blender', type=Path, default=ROOT / 'scripts/blender_python.py')
    parser.add_argument('--python-executable', default=sys.executable)
    args = parser.parse_args()
    try:
        result = render_water_slice(args.input_root, args.output_root, args.frames, args.threads,
                                    args.blender, args.python_executable)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
