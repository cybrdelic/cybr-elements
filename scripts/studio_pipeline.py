#!/usr/bin/env python3
"""Restore authentic inputs, solve fresh state, and render a studio review/film.

Review uses selected original 30fps frame IDs; complete production requires
every native frame. Previous videos never enter the renderer or encoder.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from render_studio import frame_selection
from rerender_batch import ELEMENTS, restore

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/'scripts'


def run(command, log):
    print('Stage', log.name, flush=True)
    with log.open('w') as stream:
        p = subprocess.run(list(map(str, command)), stdout=stream, stderr=subprocess.STDOUT)
    if p.returncode:
        raise RuntimeError(log.read_text(errors='replace')[-4000:])


def water_state(output, threads, frames, cache=None):
    source = ROOT/'work/element-motion'
    ground = source/'sigil-02-bending-ground/full'
    if cache:
        physical = cache.resolve()
        if not (physical/'particles/manifest.json').is_file():
            raise FileNotFoundError('Explicit water cache has no complete particle manifest')
        manifest = json.loads((physical/'particles/manifest.json').read_text())
        if len(manifest['frames']) != 240:
            raise ValueError('Use a complete freshly solved 240-frame water cache')
    else:
        physical = output/'water-state'; physical.mkdir()
        config = json.loads((source/'sigil-02-active-elements/water-full/config.json').read_text())
        config.update(forceRoot=str(ground), sourceRoot=str(ground))
        (physical/'config.json').write_text(json.dumps(config, indent=2)+'\n')
        for name in ('parcels.f32', 'guides.npz'):
            shutil.copy2(ground/name, physical/name)
        run(['node', source/'sigil_02_active_water.mjs', '--full', '--offline', '--output', physical,
             '--force-root', ground], output/'water-solve.log')
    run([sys.executable, source/'sigil_02_active_mesh.py', '--full', '--offline', '--output', physical,
         '--frames', ','.join(map(str, frames))], output/'water-mesh.log')
    return physical


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind', choices=ELEMENTS, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--quality', choices=('review', 'hero', 'production'), default='review')
    p.add_argument('--frames', type=frame_selection)
    p.add_argument('--width', type=int)
    p.add_argument('--height', type=int)
    p.add_argument('--samples', type=int)
    p.add_argument('--threads', type=int, default=4)
    p.add_argument('--water-cache', type=Path, help='Explicit complete fresh particle cache from this renderer revision')
    p.add_argument('--hero-frame', type=int, help='Additionally render this selected state at 1280x720, 64 samples')
    a = p.parse_args()
    a.output = a.output.resolve()
    if a.output.exists() and any(a.output.iterdir()):
        p.error('Choose a fresh output directory')
    count = 240 if a.kind == 'water' else 294 if a.kind in ('fire', 'air') else 300
    hero = {'water': 184, 'earth': 170, 'lightning': 140}.get(a.kind, 134)
    frames = a.frames or ([hero] if a.quality == 'hero' else list(range(count)) if a.quality == 'production'
                         else list(range(90, 150, 2)))
    if max(frames) >= count:
        p.error('Frame selection exceeds the native timeline')
    if a.hero_frame is not None and a.hero_frame not in frames:
        p.error('The hero state must be among the selected native frames')
    width = a.width or (640 if a.quality == 'review' else 1280)
    height = a.height or (360 if a.quality == 'review' else 720)
    samples = a.samples or (32 if a.quality == 'review' else 128)
    if min(width, height, samples, a.threads) <= 0 or width % 2 or height % 2:
        p.error('Use positive sampling/thread counts and even image dimensions')
    a.output.mkdir(parents=True, exist_ok=True)
    inputs = restore(a.kind, ROOT)
    selected = ','.join(map(str, frames))
    if a.kind in ('fire', 'air'):
        volume = a.output/'volumes'
        grid = [320, 64, 180] if a.quality == 'production' else [320, 48, 180]
        run([sys.executable, SCRIPTS/'prepare_studio_gas.py', '--kind', a.kind, '--output', volume,
             '--grid', *grid, '--frames', *frames, '--threads', a.threads], a.output/'gas-solve.log')
    elif a.kind == 'lightning':
        volume = a.output/'volumes'
        run([sys.executable, SCRIPTS/'prepare_studio_lightning.py', '--output', volume,
             '--frames', *frames], a.output/'gas-solve.log')
        volume = volume/'materials/lightning/vdb'
    else:
        volume = None
    render_root = a.output/'render'
    if a.kind == 'water':
        physical = water_state(a.output, a.threads, frames, a.water_cache)
        render_root.mkdir(); images = render_root/'frames'
        source = ROOT/'work/element-motion/sigil_02_active_water_render.py'
        run([sys.executable, SCRIPTS/'blender_python.py', '--background', '--python', source, '--',
             '--full', '--studio', '--output', physical, '--render-output', images,
             '--width', width, '--height', height, '--samples', samples, '--threads', a.threads,
             '--device', 'cpu', '--frames', selected, '--keep-cache'], a.output/'render.log')
    else:
        command = [sys.executable, SCRIPTS/'render_studio.py', '--kind', a.kind, '--output', render_root,
                   '--frames', selected, '--width', width, '--height', height,
                   '--samples', samples, '--threads', a.threads]
        if volume:
            command += ['--volume-root', volume]
        run(command, a.output/'render.log')
        images = render_root/'frames'
    delivered = a.output/'delivery'; delivered.mkdir()
    from PIL import Image
    hashes = {}
    for f in frames:
        found = list(images.glob(f'{f:04d}.*'))
        if len(found) != 1:
            raise RuntimeError('Every requested native frame must be delivered exactly once')
        image = found[0]
        with Image.open(image) as im:
            im.load()
            if im.size != (width, height):
                raise RuntimeError('Renderer delivered unexpected image dimensions')
        target = delivered/image.name
        shutil.copy2(image, target)
        hashes[str(f)] = hashlib.sha256(target.read_bytes()).hexdigest()
    hero_info = None
    if a.hero_frame is not None:
        hero_root = a.output/'hero-render'
        if a.kind == 'water':
            hero_root.mkdir()
            command = [sys.executable, SCRIPTS/'blender_python.py', '--background', '--python', source, '--',
                       '--full', '--studio', '--output', physical, '--render-output', hero_root,
                       '--width', 1280, '--height', 720, '--samples', 64, '--threads', a.threads,
                       '--device', 'cpu', '--frames', a.hero_frame, '--keep-cache']
            hero_images = hero_root
        else:
            command = [sys.executable, SCRIPTS/'render_studio.py', '--kind', a.kind, '--output', hero_root,
                       '--frames', a.hero_frame, '--width', 1280, '--height', 720,
                       '--samples', 64, '--threads', a.threads]
            if volume:
                command += ['--volume-root', volume]
            hero_images = hero_root/'frames'
        run(command, a.output/'hero-render.log')
        found = list(hero_images.glob(f'{a.hero_frame:04d}.*'))
        if len(found) != 1:
            raise RuntimeError('The hero renderer must deliver exactly one native state')
        with Image.open(found[0]) as im:
            im.load()
            if im.size != (1280, 720):
                raise RuntimeError('Unexpected hero image dimensions')
            im.convert('RGB').save(delivered/'hero.png')
        hero_info = {'native_frame': a.hero_frame, 'resolution': [1280, 720], 'samples': 64,
                     'image_sha256': hashlib.sha256((delivered/'hero.png').read_bytes()).hexdigest()}
    report = {'kind': a.kind, 'quality': a.quality, 'native_fps': 30, 'frames': frames,
              'resolution': [width, height], 'samples': samples, 'fresh_rendered_pixels': True,
              'old_film_pixels_used': False, 'image_sha256': hashes, 'input_sha256': inputs,
              'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
                                for f in sorted(SCRIPTS.glob('*studio*.py'))},
              'water_mesh_history': 'Selected native particle states reconstructed in ascending order; sparse studies differ from the full sequence reconstruction history' if a.kind == 'water' else None,
              'complete_native_film': frames == list(range(count))}
    report['hero'] = hero_info
    (delivered/'review-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Fresh studio frames:', delivered, flush=True)


if __name__ == '__main__':
    main()
