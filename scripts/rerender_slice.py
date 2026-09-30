#!/usr/bin/env python3
"""Produce a fresh, independently verifiable frame slice at full-film quality.

Every shard rebuilds the complete physical timeline before selecting its image
frames. Original frame numbers are retained; assembling shards never retimes
their pixels. No existing films or research caches are adopted as output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
# Retained command-line modules also use sibling imports when loaded as a
# package by the CPU-only integration tests.
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import rerender_batch

KINDS = ('earth', 'water', 'ice', 'lava', 'lightning')


def validate_range(kind: str, start: int, end: int) -> list[int]:
    if kind not in KINDS:
        raise ValueError('Unknown slice element')
    count = 240 if kind == 'water' else 300
    if not 0 <= start < end <= count:
        raise ValueError(f'Frame range must satisfy 0 <= start < end <= {count}')
    return list(range(start, end))


def fresh_output(output_root: Path, kind: str, start: int, end: int) -> Path:
    validate_range(kind, start, end)
    output = Path(output_root).resolve() / f'{kind}-{start}-{end}'
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise RuntimeError('Slice output exists; select a fresh output root to preserve prior work')
    output.mkdir(parents=True, exist_ok=True)
    return output


def file_sha256(path: Path) -> str:
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical_array_sha256(array) -> str:
    """Hash numeric values and their type/shape, excluding container metadata."""
    import numpy as np
    array = np.asarray(array)
    if array.dtype.hasobject:
        raise ValueError('Object arrays are not deterministic numeric caches')
    header = json.dumps({'dtype': array.dtype.str, 'shape': list(array.shape)},
                        sort_keys=True, separators=(',', ':')).encode()
    digest = hashlib.sha256(header + b'\0')
    digest.update(np.ascontiguousarray(array).tobytes(order='C'))
    return digest.hexdigest()


def npz_array_hashes(path: Path) -> dict[str, str]:
    import numpy as np
    with np.load(path, allow_pickle=False) as arrays:
        return {name: canonical_array_sha256(arrays[name]) for name in sorted(arrays.files)}


def collect_frame_files(directory: Path, frames: list[int]) -> dict[int, Path]:
    """Require exactly the requested, decodable 720p images at original IDs."""
    from PIL import Image
    found = {}
    for path in sorted(Path(directory).iterdir()):
        if path.suffix.lower() not in ('.jpg', '.png'):
            continue
        if len(path.stem) != 4 or not path.stem.isascii() or not path.stem.isdigit() or not path.is_file():
            raise RuntimeError(f'Unexpected frame filename: {path.name}')
        frame = int(path.stem)
        if frame in found:
            raise RuntimeError(f'Duplicate delivered frame ID: {frame}')
        with Image.open(path) as image:
            image.load()
            if image.size != (1280, 720):
                raise RuntimeError(f'Unexpected frame dimensions: {path.name}: {image.size}')
            if image.format not in ('JPEG', 'PNG'):
                raise RuntimeError(f'Unexpected image format: {path.name}')
        found[frame] = path
    if set(found) != set(frames):
        raise RuntimeError(f'Slice frame IDs differ: missing {sorted(set(frames)-set(found))}, '
                           f'extra {sorted(set(found)-set(frames))}')
    return found


def tracked_source_hashes() -> dict[str, str]:
    """Use checked-in source bytes, never generated copies with shard paths."""
    result = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, check=True, capture_output=True)
    paths = [Path(os.fsdecode(name)) for name in result.stdout.split(b'\0') if name]
    sources = {path for path in paths if path.suffix in ('.py', '.js', '.mjs', '.json', '.yml', '.yaml')}
    # The runner is included during pre-commit local checks as well as CI.
    sources.add(Path('scripts/rerender_slice.py'))
    return {path.as_posix(): file_sha256(ROOT / path) for path in sorted(sources)}


def material_cache_hashes(directory: Path, native_vdb: bool) -> dict[str, str]:
    """Compare the entire independently solved timeline, not selected frames."""
    result = {}
    trajectory = directory / 'rigid-trajectories.npz'
    if trajectory.is_file():
        result.update({f'rigid-trajectories.npz/array/{name}': digest
                       for name, digest in npz_array_hashes(trajectory).items()})
    density = sorted((directory / 'density').glob('*.png'))
    if [path.stem for path in density] != [f'{frame:04d}' for frame in range(300)]:
        raise RuntimeError('Complete 300-frame fresh density cache is required for shard comparison')
    result.update({f'density/{path.name}': file_sha256(path) for path in density})
    if native_vdb:
        import numpy as np
        from density_vdb import vdb
        report = json.loads((directory / 'atmosphere.json').read_text())
        shape = tuple(report['grid'])
        grids = sorted((directory / 'vdb').glob('*.vdb'))
        if [path.stem for path in grids] != [f'{frame:04d}' for frame in range(300)]:
            raise RuntimeError('Complete 300-frame native density cache is required')
        for path in grids:
            grid = vdb.read(str(path), 'density')
            array = np.zeros(shape, np.float32)
            grid.copyToArray(array)
            result[f'vdb/{path.stem}/density-array'] = canonical_array_sha256(array)
            # A different placement cannot pass by sharing the same values.
            endpoints = np.asarray([grid.transform.indexToWorld((0, 0, 0)),
                                    grid.transform.indexToWorld(tuple(size - 1 for size in shape))], np.float64)
            result[f'vdb/{path.stem}/world-endpoints'] = canonical_array_sha256(endpoints)
            del grid
    return result


def produce(args, output: Path, frames: list[int]) -> tuple[Path, dict, dict]:
    """Return the image directory, full numeric cache identities and mapping."""
    source = ROOT / 'work/element-motion'
    python = sys.executable
    ids = ','.join(map(str, frames))
    if args.kind == 'earth':
        stage = output / 'earth'
        rerender_batch.checked([args.blender, '--background', '--python', SCRIPTS / 'rerender_earth.py', '--',
                                '--mode', 'full', '--film-frames', ids, '--skip-encode',
                                '--source-root', source, '--input-root', args.input_root / 'work/element-motion',
                                '--output', stage, '--width', 1280, '--height', 720, '--samples', 16,
                                '--threads', args.threads, '--engine', 'cycles'], output / 'render.log')
        report = json.loads((stage / 'render-report.json').read_text())
        trajectory_hash = report.get('physicsTrajectorySha256')
        if not trajectory_hash:
            raise RuntimeError('Earth slice must record its complete Bullet trajectory identity')
        mapping = {str(frame): report['outputFrameMap'][frame] for frame in frames}
        return stage / 'frames', {'earth/full-bullet-trajectory': trajectory_hash}, mapping
    if args.kind == 'water':
        from water_slice import render_water_slice
        result = render_water_slice(input_root=args.input_root, output_root=output / 'water',
                                    frames=frames, threads=args.threads, blender=args.blender,
                                    python_executable=python)
        cache = result['cacheHashes']
        if set(cache.get('frames', {})) != {f'{frame:04d}' for frame in range(240)}:
            raise RuntimeError('Water slice must record its complete physical cache identity')
        identities = {'water/physical-config': cache['configSha256'],
                      'water/full-cache': cache['sha256']}
        for frame, payloads in sorted(cache['frames'].items()):
            if set(payloads) != {'particles', 'mesh', 'velocity'}:
                raise RuntimeError('Water slice physical cache fields are incomplete')
            identities.update({f'water/{frame}/{name}': digest for name, digest in payloads.items()})
        return Path(result['framesDirectory']), identities, {}
    material_root = output / 'materials'
    common = [args.kind, '--source-root', source, '--input-root', args.input_root / 'work/element-motion',
              '--output-root', material_root, '--blender', args.blender, '--python', python,
              '--threads', args.threads, '--samples', 64 if args.kind == 'lightning' else 24,
              '--width', 1280, '--height', 720, '--engine', 'eevee' if args.kind == 'lightning' else 'cycles',
              '--native-vdb' if args.kind == 'lightning' else '--atlas-volume']
    for action in ('prepare', 'physics', 'atmosphere', 'render'):
        command = [python, SCRIPTS / 'render_materials.py', action, *common]
        if action == 'render':
            command += ['--frames', ids]
        rerender_batch.checked(command, output / f'{action}.log')
    stage = material_root / args.kind
    return stage / 'frames', material_cache_hashes(stage, args.kind == 'lightning'), {}


def settings(kind: str, threads: int) -> dict:
    value = {'resolution': [1280, 720], 'fps': 30, 'threads': threads,
             'samples': 16 if kind == 'earth' else 64 if kind == 'lightning' else 24,
             'engine': 'BLENDER_EEVEE_NEXT' if kind == 'lightning' else 'CYCLES'}
    if kind in ('ice', 'lava', 'lightning'):
        value['volumeFormat'] = 'native-vdb' if kind == 'lightning' else 'atlas'
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=KINDS, required=True)
    parser.add_argument('--start', type=int, required=True, help='Inclusive original film frame ID')
    parser.add_argument('--end', type=int, required=True, help='Exclusive original film frame ID')
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--input-root', type=Path, default=ROOT)
    parser.add_argument('--output-root', type=Path, default=ROOT / 'work/render-slices')
    parser.add_argument('--blender', type=Path, default=SCRIPTS / 'blender_python.py')
    args = parser.parse_args()
    try:
        frames = validate_range(args.kind, args.start, args.end)
    except ValueError as error:
        parser.error(str(error))
    if not 1 <= args.threads <= 64:
        parser.error('threads must be between 1 and 64')
    args.input_root = args.input_root.resolve()
    args.blender = args.blender.resolve()
    begun = time.monotonic()
    output = fresh_output(args.output_root, args.kind, args.start, args.end)
    inputs = rerender_batch.restore(args.kind, args.input_root)
    images, cache_hashes, mapping = produce(args, output, frames)
    found = collect_frame_files(images, frames)
    delivery = output / 'delivery'
    delivered_frames = delivery / 'frames'
    delivered_frames.mkdir(parents=True)
    frame_hashes = {}
    for frame, path in sorted(found.items()):
        target = delivered_frames / path.name
        shutil.copy2(path, target)
        frame_hashes[target.relative_to(delivery).as_posix()] = file_sha256(target)
    report_hashes = {}
    # Reports retain stage-relative paths and names; their timestamps/paths are
    # verified as artifacts, but are not compared as physical shard identities.
    for report in sorted(output.rglob('*.json')):
        if report.is_relative_to(delivery):
            continue
        target = delivery / 'reports' / report.relative_to(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(report, target)
        report_hashes[target.relative_to(delivery).as_posix()] = file_sha256(target)
    receipt = {'version': 1, 'kind': args.kind, 'start': args.start, 'end': args.end,
               'frameIDs': frames, 'sourceCommit': os.environ.get('GITHUB_SHA'),
               'settings': settings(args.kind, args.threads), 'inputSha256': inputs,
               'sourceSha256': tracked_source_hashes(), 'cacheSha256': cache_hashes,
               'physicsSha256': cache_hashes, 'frameSha256': frame_hashes,
               'reportSha256': report_hashes, 'frameMapping': mapping,
               'freshPixels': True, 'oldFilmPixelsUsed': False,
               'elapsedSeconds': time.monotonic() - begun}
    (delivery / 'slice-summary.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'complete': True, 'delivery': str(delivery), 'frameIDs': frames}, indent=2), flush=True)


if __name__ == '__main__':
    main()
