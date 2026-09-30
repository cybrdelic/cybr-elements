#!/usr/bin/env python3
"""Encode actual studio shards at their native time spacing, with verified pixels."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from PIL import Image, ImageDraw, ImageFont

ELEMENTS = ('water', 'fire', 'earth', 'air', 'ice', 'lava', 'lightning')
HERO_TARGET = {'water': 135, 'earth': 170, 'lightning': 140}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(roots):
    result = {kind: {'frames': {}, 'heroes': [], 'reports': []} for kind in ELEMENTS}
    for root in roots:
        for path in sorted(root.rglob('review-report.json')):
            report = json.loads(path.read_text())
            kind = report['kind']
            if kind not in result or not report.get('fresh_rendered_pixels') or report.get('old_film_pixels_used'):
                raise ValueError(f'Unexpected render provenance: {path}')
            group = result[kind]
            group['reports'].append(report)
            for frame in report['frames']:
                images = [p for p in path.parent.glob(f'{frame:04d}.*') if p.suffix.lower() in ('.png', '.jpg')]
                if len(images) != 1:
                    raise ValueError(f'Expected exactly one delivered image for {kind}/{frame}')
                image = images[0]
                if digest(image) != report['image_sha256'][str(frame)]:
                    raise ValueError(f'Rendered image hash mismatch: {image}')
                if frame in group['frames']:
                    raise ValueError(f'Duplicate native state: {kind}/{frame}')
                with Image.open(image) as im:
                    im.load()
                    if list(im.size) != report['resolution']:
                        raise ValueError(f'Incorrect image dimensions: {image}')
                group['frames'][frame] = image
            if report.get('hero'):
                hero = path.parent/'hero.png'
                if digest(hero) != report['hero']['image_sha256']:
                    raise ValueError(f'Hero pixel hash mismatch: {hero}')
                with Image.open(hero) as im:
                    im.load()
                    if list(im.size) != report['hero']['resolution']:
                        raise ValueError(f'Incorrect hero dimensions: {hero}')
                group['heroes'].append((report['hero']['native_frame'], hero))
    for kind, group in result.items():
        frames = sorted(group['frames'])
        if len(frames) < 2 or not group['heroes']:
            raise ValueError(f'Incomplete element delivery: {kind}')
        deltas = {b-a for a, b in zip(frames, frames[1:])}
        if len(deltas) != 1:
            raise ValueError(f'Native timeline has a gap: {kind}')
        if len({tuple(r['resolution']) for r in group['reports']}) != 1:
            raise ValueError(f'Mixed image dimensions: {kind}')
        if any(r['native_fps'] != 30 for r in group['reports']):
            raise ValueError(f'Unexpected source frame rate: {kind}')
        # Each shard must use the same renderer, materials and numerical code.
        required = ('scripts/studio_scene.py', 'scripts/render_studio.py', 'scripts/studio_lava.py')
        for name in required:
            if len({r['source_sha256'][name] for r in group['reports']}) != 1:
                raise ValueError(f'Mixed renderer revisions: {kind}/{name}')
        group['ids'], group['step'] = frames, deltas.pop()
        if group['step'] not in (1, 2):
            raise ValueError(f'Unsupported review sampling: {kind}')
    return result


def assemble(groups, output):
    output.mkdir(parents=True, exist_ok=False)
    exports = []
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', 21)
    except OSError:
        font = ImageFont.load_default(size=21)
    sheet = Image.new('RGB', (1440, 1800), '#090c10')
    draw = ImageDraw.Draw(sheet)
    for i, kind in enumerate(ELEMENTS):
        group = groups[kind]
        fps = 30//group['step']
        video = output/f'cybr-elements-{kind}-studio-review.mp4'
        with tempfile.TemporaryDirectory(prefix='cybr-review-') as directory:
            staging = Path(directory)
            for number, frame in enumerate(group['ids']):
                source = group['frames'][frame]
                with Image.open(source) as im:
                    im.convert('RGB').save(staging/f'{number:04d}.png')
            subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-framerate', str(fps),
                            '-i', str(staging/'%04d.png'), '-frames:v', str(len(group['ids'])),
                            '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p',
                            '-movflags', '+faststart', str(video)], check=True)
        info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                                  '-show_entries', 'stream=width,height,nb_frames,avg_frame_rate:format=duration',
                                                  '-of', 'json', str(video)], text=True))
        stream = info['streams'][0]
        resolution = group['reports'][0]['resolution']
        if ([stream['width'], stream['height']] != resolution or
                int(stream['nb_frames']) != len(group['ids']) or stream['avg_frame_rate'] != f'{fps}/1'):
            raise ValueError(f'Encoded timing/dimensions mismatch: {kind}')
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', str(video), '-f', 'null', '-'], check=True)
        frame, source = min(group['heroes'], key=lambda x: abs(x[0]-HERO_TARGET.get(kind, 134)))
        hero = output/f'cybr-elements-{kind}-studio.png'
        shutil.copy2(source, hero)
        x, y = (i%2)*720, (i//2)*450
        draw.text((x+20, y+12), kind.upper(), font=font, fill='#edf3f8')
        with Image.open(hero) as im:
            sheet.paste(im.resize((720, 405), Image.Resampling.LANCZOS), (x, y+42))
        exports.append({'element': kind, 'video': video.name, 'hero': hero.name,
                        'native_frames': group['ids'], 'hero_native_frame': frame,
                        'fps': fps, 'resolution': resolution,
                        'duration_seconds': len(group['ids'])/fps,
                        'complete_native_film': all(r['complete_native_film'] for r in group['reports']),
                        'video_sha256': digest(video), 'hero_sha256': digest(hero),
                        'fully_decoded': True, 'render_provenance': group['reports']})
    sheet.save(output/'cybr-elements-studio-contact-sheet.png')
    (output/'render-provenance.json').write_text(json.dumps(exports, indent=2)+'\n')
    with zipfile.ZipFile(output/'cybr-elements-studio-renders.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path.suffix != '.zip':
                archive.write(path, path.name)
    print(json.dumps([{k: row[k] for k in ('element', 'fps', 'resolution', 'duration_seconds', 'fully_decoded')}
                      for row in exports], indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a fresh output directory')
    assemble(collect(args.inputs), args.output.resolve())


if __name__ == '__main__':
    main()
