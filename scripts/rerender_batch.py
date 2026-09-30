#!/usr/bin/env python3
"""Restore verified inputs and produce one fresh, bounded CPU element film.

This entry point never replaces the current player films. The per-material
renderers retain the authored motion and numerical algorithms documented in
docs/PIPELINES.md; settings and actual source hashes accompany each new film.
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

import fetch_assets

ROOT = Path(__file__).resolve().parents[1]
ELEMENTS = ('fire', 'water', 'earth', 'air', 'ice', 'lava', 'lightning')
BASE = 'work/element-motion/'


def retained_inputs(kind):
    if kind not in ELEMENTS:
        raise ValueError('Unknown element')
    if kind == 'water':
        return {BASE + 'sigil-02-bending-ground/full/' + name
                for name in ['parcels.f32', 'guides.npz', 'guide-0.f32', 'guide-1.f32', 'guide-2.f32']}
    paths = set()
    if kind != 'earth':
        paths.add(BASE + 'sigil-02-v2/source.npz')
    if kind == 'lightning':
        paths.add(BASE + 'sigil-02-active-elements/lightning/channels.json')
    if kind in ('earth', 'ice', 'lava'):
        paths.add(BASE + 'sigil-02-coherent/earth-geometry.json')
    if kind in ('earth', 'lava'):
        for texture in (['diff', 'arm', 'nor_gl'] if kind == 'earth' else ['diff', 'nor_gl']):
            paths.add(BASE + f'sigil-02-repair/scans/rock_09/textures/rock_09_{texture}_2k.jpg')
    return paths


def restore(kind, input_root):
    manifest = json.loads((ROOT / 'docs/assets.json').read_text())
    wanted = retained_inputs(kind)
    assets = [asset for asset in manifest['assets'] if asset['path'] in wanted]
    if {asset['path'] for asset in assets} != wanted:
        raise RuntimeError('The published inventory is missing required retained inputs')
    packs = {asset['pack'] for asset in assets}
    subset = dict(manifest, assets=assets, packs=[pack for pack in manifest['packs'] if pack['name'] in packs])
    fetch_assets.validate_manifest(subset, require_archive_integrity=True)
    input_root.mkdir(parents=True, exist_ok=True)
    previous = fetch_assets.ROOT
    try:
        fetch_assets.ROOT = input_root
        fetch_assets.restore_assets(subset, all_assets=True)
    finally:
        fetch_assets.ROOT = previous
    return {asset['path']: asset['sha256'] for asset in assets}


def checked(command, log):
    print('RUN ' + ' '.join(map(str, command)), flush=True)
    with log.open('w') as stream:
        result = subprocess.run(list(map(str, command)), stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        tail = '\n'.join(log.read_text(errors='replace').splitlines()[-30:])
        raise RuntimeError(f'Render stage failed ({result.returncode}): {log}\n{tail}')


def film_probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                             '-show_entries', 'stream=width,height,avg_frame_rate,nb_read_frames,duration',
                             '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)['streams'][0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=ELEMENTS, required=True)
    parser.add_argument('--input-root', type=Path, default=ROOT)
    parser.add_argument('--output-root', type=Path, default=ROOT / 'work/rerenders')
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--blender', type=Path, default=ROOT / 'scripts/blender_python.py')
    parser.add_argument('--preflight', action='store_true', help='List the exact required release inputs only')
    args = parser.parse_args()
    if args.threads < 1 or args.threads > 64:
        parser.error('threads must be between 1 and 64')
    if args.preflight:
        print(json.dumps({'element': args.kind, 'retainedInputs': sorted(retained_inputs(args.kind))}, indent=2))
        return
    started = time.monotonic()
    output = args.output_root.resolve() / args.kind
    if output.exists() and any(output.iterdir()):
        raise RuntimeError('Render output exists; select a fresh output root to preserve all prior frames')
    output.mkdir(parents=True, exist_ok=True)
    delivery = output / 'delivery'
    if delivery.exists() and any(delivery.iterdir()):
        raise RuntimeError('Completed delivery exists; select a fresh output root')
    delivery.mkdir(exist_ok=True)
    inputs = restore(args.kind, args.input_root.resolve())
    python = sys.executable
    scripts = ROOT / 'scripts'
    source = ROOT / BASE
    reports = []
    if args.kind in ('fire', 'air'):
        gas_output = output / 'gas'
        checked([python, scripts / 'rerender_gas.py', '--kind', args.kind, '--repo', ROOT,
                 '--source', args.input_root / BASE / 'sigil-02-v2/source.npz', '--output', gas_output,
                 '--grid', 320, 32, 180, '--resolution', 1280, 720, '--fps', 30, '--frames', 294,
                 '--substeps', 3, '--threads', args.threads, '--save-every', 30], output / 'render.log')
        movie = gas_output / f'{args.kind}-02-cpu.mp4'
        reports = [gas_output / 'render-report.json']
    elif args.kind == 'earth':
        earth_output = output / 'earth'
        checked([args.blender, '--background', '--python', scripts / 'rerender_earth.py', '--',
                 '--mode', 'full', '--source-root', source, '--input-root', args.input_root / BASE,
                 '--output', earth_output, '--width', 1280, '--height', 720, '--samples', 16,
                 '--threads', args.threads, '--engine', 'cycles'], output / 'render.log')
        movie = earth_output / 'earth-02-r7-cpu720.mp4'
        reports = [earth_output / 'render-report.json', earth_output / 'render-settings.json']
    elif args.kind == 'water':
        water_output = output / 'water'
        water_output.mkdir(exist_ok=True)
        ground = (args.input_root / BASE / 'sigil-02-bending-ground/full').resolve()
        config = json.loads((source / 'sigil-02-active-elements/water-full/config.json').read_text())
        config.update(forceRoot=str(ground), sourceRoot=str(ground))
        (water_output / 'config.json').write_text(json.dumps(config, indent=2))
        for name in ['parcels.f32', 'guides.npz']:
            shutil.copy2(ground / name, water_output / name)
        checked(['node', source / 'sigil_02_active_water.mjs', '--full', '--offline', '--output', water_output,
                 '--force-root', ground], output / 'solve.log')
        checked([python, source / 'sigil_02_active_mesh.py', '--full', '--offline', '--output', water_output], output / 'mesh.log')
        checked([args.blender, '--background', '--python', source / 'sigil_02_active_water_render.py', '--',
                 '--full', '--output', water_output, '--render-output', water_output / 'frames',
                 '--width', 1280, '--height', 720, '--samples', 24, '--threads', args.threads,
                 '--device', 'cpu', '--keep-cache'], output / 'render.log')
        movie = water_output / 'water-02-r9-cpu720.mp4'
        checked(['ffmpeg', '-v', 'error', '-y', '-framerate', 30, '-i', water_output / 'frames/%04d.jpg',
                 '-frames:v', 240, '-c:v', 'libx264', '-preset', 'slow', '-crf', 17,
                 '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-threads', args.threads, movie], output / 'encode.log')
        reports = [water_output / 'config.json', water_output / 'particles/manifest.json', water_output / 'mesh/manifest.json']
    else:
        material_root = output / 'materials'
        material_samples = 64 if args.kind == 'lightning' else 24
        checked([python, scripts / 'render_materials.py', 'all', args.kind, '--source-root', source,
                 '--input-root', args.input_root / BASE, '--output-root', material_root,
                 '--blender', args.blender, '--python', python, '--threads', args.threads,
                 '--samples', material_samples, '--width', 1280, '--height', 720], output / 'render.log')
        movie = material_root / args.kind / f'{args.kind}-cpu-revised.mp4'
        reports = [material_root / args.kind / name for name in ['render-report.json', 'atmosphere.json', 'physics-report.json']]
        reports.append(material_root / 'pipeline/source-receipt.json')
    expected_frames = 294 if args.kind in ('fire', 'air') else 240 if args.kind == 'water' else 300
    probe = film_probe(movie)
    if (int(probe['nb_read_frames']) != expected_frames or probe['avg_frame_rate'] != '30/1'
            or [probe['width'], probe['height']] != [1280, 720]):
        raise RuntimeError('Fresh film has unexpected frame count, cadence or resolution')
    checked(['ffmpeg', '-v', 'error', '-xerror', '-i', movie, '-f', 'null', '-'], output / 'decode.log')
    target = delivery / f'cybr-elements-{args.kind}-rerender.mp4'
    shutil.copy2(movie, target)
    for index, report in enumerate(reports):
        if report.is_file():
            shutil.copy2(report, delivery / f'{index:02d}-{report.name}')
    with target.open('rb') as movie_stream:
        movie_hash = hashlib.file_digest(movie_stream, 'sha256').hexdigest()
    source_paths = set(scripts.glob('rerender_*.py')) | set(source.glob('sigil_02_active_*.*'))
    source_paths.update(scripts / name for name in ['render_materials.py', 'material_volume_adapter.py', 'density_vdb.py', 'blender_python.py', 'run_bpy_script.py'])
    source_paths.update(source / name for name in ['sigil_02_atmosphere.py', 'gas_projection.py', 'sigil_02_fire_v2.py', 'sigil_02_air_v2.py', 'sigil_02_ground_earth_render.py', 'sigil_02_new_materials.py'])
    receipt = dict(element=args.kind, sourceCommit=os.environ.get('GITHUB_SHA'),
                   elapsedSeconds=time.monotonic()-started, nativeResolution=[1280, 720], fps=30,
                   frames=expected_frames, inputSha256=inputs, freshFrames=True, oldFilmPixelsUsed=False,
                   movieSha256=movie_hash,
                   sourceSha256={str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in sorted(source_paths)}, probe=probe)
    (delivery / 'render-summary.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'complete': True, 'film': str(target), 'frames': expected_frames}, indent=2), flush=True)


if __name__ == '__main__':
    main()
