#!/usr/bin/env python3
"""Render genuine material/flow look-development with a shared physical studio.

Native source frame IDs remain in filenames. Sparse frame selections are
review studies; they are never substituted for a complete 30fps film.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def frame_selection(value):
    if ':' in value:
        numbers = [int(x) for x in value.split(':')]
        if len(numbers) not in (2, 3):
            raise argparse.ArgumentTypeError('Use start:end[:step] or comma-separated IDs')
        result = list(range(*numbers))
    else:
        result = [int(x) for x in value.split(',')]
    if not result or len(result) != len(set(result)) or min(result) < 0 or max(result) > 299:
        raise argparse.ArgumentTypeError('Choose unique frame IDs in 0..299')
    return sorted(result)


def scene_settings(scene, a):
    scene.render.resolution_x, scene.render.resolution_y = a.width, a.height
    scene.render.resolution_percentage = 100
    scene.render.threads_mode = 'FIXED'; scene.render.threads = a.threads
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.render.fps = 30
    scene.cycles.samples = a.samples


def retained_material_scene(a):
    import bpy
    from render_materials import portable_sources
    from rerender_earth import iter_action_fcurves

    output = a.output/'retained-materials'
    source = ROOT/'work/element-motion'
    os.environ.update(CYBR_ELEMENT_SOURCE_ROOT=str(source), CYBR_MATERIAL_DIR=str(output),
                      CYBR_WIDTH=str(a.width), CYBR_HEIGHT=str(a.height),
                      CYBR_SAMPLES=str(a.samples), CYBR_THREADS=str(a.threads),
                      CYBR_RENDER_ENGINE='cycles', CYBR_NATIVE_VDB='0')
    render, _ = portable_sources(source, a.output/'pipeline')
    setup = render.read_text().split('old=None;rows=[];begun=time.time();trajectory=', 1)[0]
    setup = setup.replace('o.animation_data.action.fcurves', 'iter_action_fcurves(o)')
    original = sys.argv
    sys.argv = [str(render), '--', a.kind, '--full']
    try:
        if bpy.context.scene.world is None:
            bpy.context.scene.world = bpy.data.worlds.new('Material world')
        if a.kind == 'lightning':
            target = output/'lightning/channels.json'; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((source/'sigil-02-active-elements/lightning/channels.json').read_bytes())
        ns = {'__file__': str(render), 'iter_action_fcurves': iter_action_fcurves}
        exec(compile(setup, str(render), 'exec'), ns)
    finally:
        sys.argv = original
    ns['cloud'].hide_render = True
    return ns


def render(a):
    import bpy
    from mathutils import Vector
    from studio_scene import Studio, gas_volume, configure_lightning, update_lightning

    started = time.monotonic()
    a.output.mkdir(parents=True, exist_ok=True)
    frames_dir = a.output/'frames'; frames_dir.mkdir(exist_ok=True)
    rows = []
    ns = None; flow = None; obj = None; material = None; origin = None
    if a.kind == 'ice' or a.kind == 'lightning':
        ns = retained_material_scene(a)
        scene = ns['s']
        studio = Studio(scene, a.kind, samples=a.samples)
        if a.kind == 'lightning':
            configure_lightning(ns)
            if not a.volume_root:
                raise ValueError('Lightning requires freshly solved --volume-root VDB fields')
            obj = gas_volume(a.volume_root/f'{a.frames[0]:04d}.vdb', 'lightning')
    elif a.kind == 'earth':
        from rerender_earth import arguments, build_scene, preflight
        args = arguments(['--output', str(a.output/'earth-physics'), '--width', str(a.width),
                          '--height', str(a.height), '--samples', str(a.samples), '--threads', str(a.threads)])
        args.output.mkdir(parents=True, exist_ok=True)
        source, _, _ = preflight(args)
        bpy, scene, objects = build_scene(args, source)
        studio = Studio(scene, a.kind, samples=a.samples)
    else:
        bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
        scene = bpy.context.scene
        bpy.ops.object.camera_add(); scene.camera = bpy.context.object
        studio = Studio(scene, a.kind, target=(0, 0, .18) if a.kind == 'lava' else (0, 0, 2.1) if a.kind == 'fire' else (0, 0, 1.75),
                        samples=a.samples)
        if a.kind == 'lava':
            from studio_lava import LavaFilm, source_support, lava_material
            support, dx, origin = source_support(ROOT/'work/element-motion/sigil-02-v2/source.npz', a.lava_grid)
            flow = LavaFilm(support, dx)
            material = lava_material()
        elif a.kind in ('fire', 'air'):
            if not a.volume_root:
                raise ValueError('Gas requires freshly solved --volume-root VDB fields')
            obj = gas_volume(a.volume_root/f'{a.frames[0]:04d}.vdb', a.kind)
        else:
            raise ValueError('Use the retained FLIP renderer with --studio for water')
    scene_settings(scene, a)
    chosen = set(a.frames)
    for f in range(max(a.frames)+1):
        if a.kind == 'earth':
            # Use the forward authored assembly and native physical release;
            # no reversal of a breakup to make the entrance appear simulated.
            scene.frame_set(f+1)
        elif a.kind == 'ice':
            scene.frame_set(f+1)
        if flow is not None:
            flow.advance(a.lava_time_scale/30)
        if f not in chosen:
            continue
        target = frames_dir/f'{f:04d}.png'
        if target.exists():
            raise RuntimeError('Refusing to adopt an earlier image; select a fresh output')
        if flow is not None:
            from studio_lava import build_mesh_object
            obj = build_mesh_object(flow, origin, material, obj)
        if obj is not None and a.kind in ('fire', 'air', 'lightning'):
            path = a.volume_root/f'{f:04d}.vdb'
            if not path.is_file():
                raise FileNotFoundError(path)
            obj.data.filepath = str(path.resolve())
        if ns is not None and a.kind == 'lightning':
            discharge_power = update_lightning(ns, f/30)
            obj.data.materials[0].node_tree.nodes['Discharge haze power'].inputs[1].default_value = 4*discharge_power
        studio.update(f/30)
        scene.render.filepath = str(target)
        begin = time.monotonic()
        bpy.ops.render.render(write_still=True)
        row = {'frame': f, 'seconds': f/30, 'render_seconds': time.monotonic()-begin,
               'image_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
        if flow is not None:
            row['flow'] = flow.diagnostics()
        rows.append(row)
        report = {'kind': a.kind, 'renderer': bpy.app.version_string, 'engine': 'CYCLES',
                  'resolution': [a.width, a.height], 'samples': a.samples,
                  'native_fps': 30, 'selected_native_frames': a.frames,
                  'fresh_rendered_pixels': True, 'old_film_pixels_used': False,
                  'lava_time_scale': a.lava_time_scale if a.kind == 'lava' else None,
                  'lava_model': 'Conservative 2.5-D viscous Bingham film with advected enthalpy and a lumped surface boundary; nominal parameters' if flow is not None else None,
                  'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in [Path(__file__), ROOT/'scripts/studio_scene.py', ROOT/'scripts/studio_lava.py']},
                  'frames': rows, 'elapsed_seconds': time.monotonic()-started}
        (a.output/'render-report.json').write_text(json.dumps(report, indent=2)+'\n')
        print(a.kind, 'RENDER', f, 'seconds', round(time.monotonic()-started, 2), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind', choices=('earth', 'ice', 'lava', 'lightning', 'fire', 'air'), required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--volume-root', type=Path)
    p.add_argument('--frames', type=frame_selection, default=[135])
    p.add_argument('--width', type=int, default=1280)
    p.add_argument('--height', type=int, default=720)
    p.add_argument('--samples', type=int, default=128)
    p.add_argument('--threads', type=int, default=4)
    p.add_argument('--lava-grid', type=int, default=320)
    p.add_argument('--lava-time-scale', type=float, default=6.)
    a = p.parse_args()
    if min(a.width, a.height, a.samples, a.threads, a.lava_grid, a.lava_time_scale) <= 0:
        p.error('Dimensions, sampling and physical time scale must be positive')
    a.output = a.output.resolve()
    if a.output.exists() and any(a.output.iterdir()):
        p.error('Choose a fresh output directory')
    if a.volume_root:
        a.volume_root = a.volume_root.resolve()
    render(a)


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stdout.flush(); sys.stderr.flush()
        os._exit(1)
    else:
        sys.stdout.flush(); sys.stderr.flush()
        if 'bpy' in sys.modules:
            os._exit(0)
