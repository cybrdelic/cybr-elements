"""Fresh CPU material render runs derived from the retained CYBR pipelines.

No repository source or published assets are modified. Every rendered frame is
computed by Blender from rebuilt geometry, animation and freshly solved density.
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
from material_volume_adapter import VDB_SETUP, VDB_UPDATE

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
DEFAULT_SOURCE = ROOT / 'work/element-motion'
DEFAULT_INPUT = DEFAULT_SOURCE
DEFAULT_OUTPUT = ROOT / 'work/rerenders/materials'


def replace_once(source: str, before: str, after: str) -> str:
    if source.count(before) != 1:
        raise RuntimeError('Retained source changed; inspect portability adaptation: ' + before[:100])
    return source.replace(before, after, 1)


def portable_sources(source_root: Path, generated_root: Path) -> tuple[Path, Path]:
    """Preserve the numerical/shading algorithms and adapt only execution settings."""
    generated_root.mkdir(parents=True, exist_ok=True)
    render_original = (source_root / 'sigil_02_new_materials.py').read_text()
    render = replace_once(render_original, 'import bpy,math,json,sys,time,random,shutil,bisect',
                          'import bpy,math,json,sys,time,random,shutil,bisect,os\nfrom PIL import Image')
    render = replace_once(render, 'R=Path(__file__).resolve().parent;args=',
                          "R=Path(os.environ['CYBR_ELEMENT_SOURCE_ROOT']);args=")
    render = replace_once(render, "O=R/'sigil-02-active-elements'/kind;out=", 
                          "O=Path(os.environ['CYBR_MATERIAL_DIR'])/kind;out=")
    # The original chooses full settings and an NVIDIA backend together. Keep
    # all 300 frames, but use a portable CPU backend and configurable sampling.
    backend_begin = render.index('if full:\n s.cycles.denoiser=')
    backend_end = render.index("s.world.use_nodes=True", backend_begin)
    render = render[:backend_begin] + """
s.render.engine='CYCLES'
s.cycles.device='CPU'
s.cycles.denoiser='OPENIMAGEDENOISE'
s.cycles.samples=int(os.environ.get('CYBR_SAMPLES','24'))
s.cycles.adaptive_min_samples=min(8,s.cycles.samples)
s.cycles.adaptive_threshold=.018
s.render.threads=int(os.environ.get('CYBR_THREADS','4'))
s.render.resolution_x=int(os.environ.get('CYBR_WIDTH','1280'))
s.render.resolution_y=int(os.environ.get('CYBR_HEIGHT','720'))
if os.environ.get('CYBR_RENDER_ENGINE')=='eevee':
 s.render.engine='BLENDER_EEVEE_NEXT'
 s.eevee.taa_render_samples=s.cycles.samples
 s.eevee.volumetric_tile_size='4'
 s.eevee.volumetric_samples=64
 s.eevee.use_volumetric_shadows=True
 s.eevee.volumetric_start=10
 s.eevee.volumetric_end=28
 s.eevee.volumetric_sample_distribution=0
 s.render.use_persistent_data=False
out=O/'frames';out.mkdir(parents=True,exist_ok=True)
Image.new('RGB',(s.render.resolution_x,s.render.resolution_y),(0,0,0)).save(O/'black.jpg',quality=97)
chosen=os.environ.get('CYBR_RENDER_FRAMES','')
selected=[int(value) for value in chosen.split(',')] if chosen else list(range(300))
""" + render[backend_end:]
    render = replace_once(render,
        "renderOrder=([150]+[f for f in range(300) if f!=150]) if full and kind=='lightning' and '--volume-check' not in args else range(300)",
        'renderOrder=range(300)')
    render = replace_once(render,
        "if (not full or '--volume-check' in args) and f not in selected:continue",
        'if f not in selected:continue')
    render = replace_once(render,
        "shutil.copyfile(R/'sigil-02-active-elements/black-1080.jpg',out/f'{f:04}.jpg');continue",
        "shutil.copyfile(O/'black.jpg',out/f'{f:04}.jpg');continue")
    gate = """ if full and kind=='lightning' and f==150 and '--volume-check' not in args:
  (O/'hero-ready.json').write_text(json.dumps(dict(frame=f,path=str(out/f'{f:04}.jpg'),engine=s.render.engine)))
  while not (O/'hero-approved.json').exists():time.sleep(.5)
"""
    render = replace_once(render, gate, '')
    render = replace_once(render,
        "rendered=list(range(300)) if full and '--volume-check' not in args else selected",
        "rendered=sorted(int(p.stem) for p in out.glob('[0-9][0-9][0-9][0-9].jpg'))")
    render = replace_once(render, 'cloud.data.materials.append(vm)', 'cloud.data.materials.append(vm)\n' + VDB_SETUP)
    render = replace_once(render, " noise.inputs['W'].default_value=t*.035\n",
                          " noise.inputs['W'].default_value=t*.035\n" + VDB_UPDATE)

    gas_original = (source_root / 'sigil_02_atmosphere.py').read_text()
    gas = replace_once(gas_original, "R=Path(__file__).resolve().parent;O=R/'sigil-02-active-elements'",
                       "R=Path(os.environ['CYBR_ELEMENT_SOURCE_ROOT']);O=Path(os.environ['CYBR_MATERIAL_DIR'])")
    # Measure the actual solved field, before the absorbing edge mask. This is
    # an integration diagnostic for the corrected real-valued FFT projection.
    gas = replace_once(gas, 'rows=[]\nfor f in range(300):',
                       'rows=[];projection_checks=[];vdb_receipts=[]\nfor f in range(300):')
    gas = replace_once(gas, '  v=projector.project(v)\n', """  if f%30==0:
   before=float(np.linalg.norm(projector.divergence(v)))
  v=projector.project(v)
  if f%30==0:
   after=float(np.linalg.norm(projector.divergence(v)))
   projection_checks.append(dict(frame=f,substep=sub,before=before,after=after,relative=after/max(before,1e-20)))
""")
    gas = replace_once(gas, 'method=__doc__,rows=rows)',
                       "method=__doc__,rows=rows,projectionChecks=projection_checks,vdb=vdb_receipts,vdbMapping='XYZ solver cell centers: lo + (index + 0.5) * extent/shape')")
    gas = replace_once(gas, " Image.fromarray(np.flipud(atlas)).save(out/f'{f:04}.png',compress_level=2)",
                       """ Image.fromarray(np.flipud(atlas)).save(out/f'{f:04}.png',compress_level=2)
 if os.environ.get('CYBR_WRITE_VDB')=='1':
  from density_vdb import write_density
  vdb_receipts.append(write_density(out.parent/'vdb'/f'{f:04}.vdb',density,lo,dx))
""")

    render_path = generated_root / 'portable_material.py'
    gas_path = generated_root / 'portable_atmosphere.py'
    render_path.write_text(render)
    gas_path.write_text(gas)
    (generated_root / 'source-receipt.json').write_text(json.dumps({
        'retainedSourceRoot': str(source_root),
        'sourceSha256': {
            'sigil_02_new_materials.py': hashlib.sha256(render_original.encode()).hexdigest(),
            'sigil_02_atmosphere.py': hashlib.sha256(gas_original.encode()).hexdigest()},
        'adaptations': ['separate output revision', 'CPU OpenImageDenoise rendering',
                        '720p configurable samples and threads', 'sequential frame order',
                        'explicit frame selection', 'no machine-specific review gate',
                        'resolution-matched generated black lead/tail frames',
                        'pre-edge projection diagnostics'],
        'densitySolver': 'Retained semi-Lagrangian CPU pipeline with corrected FourierProjector',
        'frameSource': 'Fresh Blender renders from geometry, animation and solved gas; no reused film frames'
    }, indent=2) + '\n')
    return render_path, gas_path


def validate_inputs(source: Path, input_root: Path, kind: str) -> None:
    required = [input_root / 'sigil-02-v2/source.npz', source / 'gas_projection.py']
    if kind == 'lightning':
        required += [input_root / 'sigil-02-active-elements/lightning/channels.json']
    else:
        required += [input_root / 'sigil-02-coherent/earth-geometry.json']
    if kind == 'lava':
        directory = input_root / 'sigil-02-repair/scans/rock_09'
        for name in ['rock_09_diff_2k.jpg', 'rock_09_nor_gl_2k.jpg']:
            if not any(directory.rglob(name)):
                required.append(directory / 'textures' / name)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError('Missing authentic source inputs:\n' + '\n'.join(missing))


def environment(args) -> dict:
    env = os.environ.copy()
    env.update(CYBR_ELEMENT_SOURCE_ROOT=str(args.input_root.resolve()),
               CYBR_MATERIAL_DIR=str(args.output_root.resolve()),
               CYBR_WIDTH=str(args.width), CYBR_HEIGHT=str(args.height),
               CYBR_SAMPLES=str(args.samples), CYBR_THREADS=str(args.threads),
               CYBR_RENDER_ENGINE=args.engine,
               CYBR_NATIVE_VDB='1' if args.native_vdb else '0',
               CYBR_WRITE_VDB='1' if args.native_vdb else '0',
               CYBR_RENDER_FRAMES=args.frames or '',
               OMP_NUM_THREADS=str(args.threads), OPENBLAS_NUM_THREADS='2')
    if args.engine == 'eevee':
        env.update(LIBGL_ALWAYS_SOFTWARE='1', EGL_PLATFORM='surfaceless',
                   GALLIUM_DRIVER='llvmpipe', LP_NUM_THREADS=str(args.threads),
                   MESA_SHADER_CACHE_DIR=str(args.output_root / 'mesa-shader-cache'))
    env['PYTHONPATH'] = os.pathsep.join([str(args.source_root.resolve()), str(SCRIPTS), env.get('PYTHONPATH', '')])
    return env


def run(command: list[str], env: dict, log: Path) -> float:
    print('Running ' + ' '.join(command), flush=True)
    begun = time.monotonic()
    with log.open('w') as stream:
        subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT, check=True)
    seconds = time.monotonic() - begun
    print(f'Completed in {seconds:.1f}s: {log}', flush=True)
    return seconds


def blender_command(args, script: Path, *flags: str) -> list[str]:
    """Support either Blender CLI or installed bpy in the chosen Python."""
    if args.blender:
        return [args.blender, '--background', '--python', str(script), '--', args.kind, '--full', *flags]
    return [args.python, str(SCRIPTS / 'run_bpy_script.py'), str(script), '--', args.kind, '--full', *flags]


def encode(args):
    directory = args.output_root / args.kind
    frames = directory / 'frames'
    present = sorted(int(path.stem) for path in frames.glob('[0-9][0-9][0-9][0-9].jpg'))
    if present != list(range(300)):
        raise RuntimeError(f'Need all 300 fresh frames before encoding; found {len(present)}')
    movie = directory / f'{args.kind}-cpu-revised.mp4'
    command = ['ffmpeg', '-y', '-v', 'error', '-framerate', '30', '-i', str(frames / '%04d.jpg'),
               '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p',
               '-movflags', '+faststart', '-threads', str(args.threads), str(movie)]
    subprocess.run(command, check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(movie), '-f', 'null', '-'], check=True)
    print(movie, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'physics', 'atmosphere', 'render', 'all', 'encode'])
    parser.add_argument('kind', choices=['ice', 'lava', 'lightning'])
    parser.add_argument('--source-root', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--input-root', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output-root', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--blender', default=os.environ.get('BLENDER_BIN'))
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--samples', type=int, help='Default: 24 Cycles samples, 64 Eevee samples.')
    parser.add_argument('--engine', choices=['cycles', 'eevee'], help='Default: Cycles for ice/lava; Eevee for lightning.')
    volume_format=parser.add_mutually_exclusive_group()
    volume_format.add_argument('--native-vdb', dest='native_vdb', action='store_true', default=None, help='Write/read genuine full-precision VDB solver density; default for lightning.')
    volume_format.add_argument('--atlas-volume', dest='native_vdb', action='store_false', help='Use the retained texture-atlas volume shader; default for ice/lava.')
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=720)
    parser.add_argument('--frames', help='Explicit fresh render frame IDs, e.g. 150,228')
    args = parser.parse_args()
    args.engine = args.engine or ('eevee' if args.kind == 'lightning' else 'cycles')
    if args.samples is None: args.samples = 64 if args.engine == 'eevee' else 24
    if args.native_vdb is None: args.native_vdb = args.kind == 'lightning'
    if min(args.threads, args.samples, args.width, args.height) <= 0:
        parser.error('Threads, samples and image dimensions must be positive.')
    if args.width % 2 or args.height % 2:
        parser.error('Image dimensions must be even for H.264 delivery.')
    if args.frames:
        try:
            chosen = [int(value) for value in args.frames.split(',')]
            if any(frame < 0 or frame >= 300 for frame in chosen): raise ValueError()
        except ValueError:
            parser.error('--frames must list integer frame IDs from 0 through 299.')
    render, gas = portable_sources(args.source_root, args.output_root / 'pipeline')
    directory = args.output_root / args.kind
    directory.mkdir(parents=True, exist_ok=True)
    if args.kind == 'lightning':
        source = args.input_root / 'sigil-02-active-elements/lightning/channels.json'
        if source.exists() and not (directory / 'channels.json').exists():
            shutil.copy2(source, directory / 'channels.json')
    if args.action == 'prepare':
        print(json.dumps({'renderScript': str(render), 'atmosphereScript': str(gas), 'output': str(directory)}, indent=2))
        return
    if args.action == 'encode':
        encode(args)
        return
    validate_inputs(args.source_root, args.input_root, args.kind)
    env = environment(args)
    if args.action in ['physics', 'all'] and args.kind != 'lightning':
        run(blender_command(args, render, '--physics-only'), env, directory / 'physics.log')
    if args.action in ['atmosphere', 'all']:
        run([args.python, str(gas), args.kind], env, directory / 'atmosphere.log')
    if args.action in ['render', 'all']:
        run(blender_command(args, render), env, directory / 'render.log')
    if args.action == 'all' and not args.frames:
        encode(args)


if __name__ == '__main__':
    main()
