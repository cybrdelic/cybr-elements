#!/usr/bin/env python3
"""Additive, offline CPU production flow for the existing CYBR ELEMENTS 02 films.

Run `python cpu/run.py plan` first. Original files, media, and player stay untouched.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from adapter import BLENDER, GAS, IO_ONLY, Diagnostic, adapt, adapt_javascript_manifest, sha256
from assets import copy_new, restore, safe_path

ROOT = Path(__file__).resolve().parents[1]
MOTION = 'work/element-motion'
ACTIVE = MOTION + '/sigil-02-active-elements'
SOURCE = MOTION + '/sigil-02-v2/source.npz'
GEOMETRY = MOTION + '/sigil-02-coherent/earth-geometry.json'
TEXTURES = MOTION + '/sigil-02-repair/scans/rock_09/textures/'
PLAYER = 'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
ELEMENTS = ('fire', 'air', 'earth', 'water', 'ice', 'lava', 'lightning')
DRIVERS = {
    'fire': ['sigil_02_fire_v2.py'],
    'air': ['sigil_02_air_v2.py'],
    'earth': ['sigil_02_ground_earth_render.py'],
    'water': ['sigil_02_active_water.mjs', 'sigil_02_active_mesh.py',
              'sigil_02_active_water_render.py', 'bending_surface.py'],
    'ice': ['sigil_02_new_materials.py', 'sigil_02_atmosphere.py'],
    'lava': ['sigil_02_new_materials.py', 'sigil_02_atmosphere.py'],
    'lightning': ['sigil_02_new_materials.py', 'sigil_02_atmosphere.py'],
}
FULL_GRID = (896, 56, 504)


def atomic_json(path: Path, data: Any) -> None:
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def selected(values: Sequence[str]) -> list[str]:
    if not values or 'all' in values:
        if len(values) > 1:
            raise ValueError('Use all by itself, or name individual elements')
        return list(ELEMENTS)
    if any(value not in ELEMENTS for value in values):
        raise ValueError('Unknown element')
    return list(dict.fromkeys(values))


def cpu_environment(threads: int) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        'CUDA_VISIBLE_DEVICES': '', 'HIP_VISIBLE_DEVICES': '', 'ROCR_VISIBLE_DEVICES': '',
        'NVIDIA_VISIBLE_DEVICES': 'none', 'ONEAPI_DEVICE_SELECTOR': '*:cpu',
        'OMP_NUM_THREADS': str(threads), 'MKL_NUM_THREADS': str(threads),
        'OPENBLAS_NUM_THREADS': str(threads), 'NUMBA_NUM_THREADS': str(threads),
        'PYTHONUNBUFFERED': '1', 'PYTHONDONTWRITEBYTECODE': '1',
        'LIBGL_ALWAYS_SOFTWARE': '1', 'GALLIUM_DRIVER': 'llvmpipe',
        '__GLX_VENDOR_LIBRARY_NAME': 'mesa',
    })
    # A caller cannot bypass the software-renderer probe by exporting a flag.
    env.pop('CYBR_EEVEE_SOFTWARE_VERIFIED', None)
    return env


def isolated_output(root: Path, requested: Path) -> Path:
    root, output = root.resolve(), requested.expanduser().resolve()
    if output == root or output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError('Output must be a separate directory outside, and not above, the checkout')
    if output.exists():
        raise FileExistsError(f'Output already exists; choose a new revision directory: {output}')
    return output


def executable(name: str, explicit: str | None = None) -> str:
    value = explicit or name
    found = shutil.which(value)
    if not found and explicit and Path(value).is_file():
        found = str(Path(value).resolve())
    if not found:
        raise FileNotFoundError(f'Required executable not found: {value}')
    return found


def force_root(root: Path) -> str:
    config_path = root / ACTIVE / 'water-full/config.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    raw = config['forceRoot'].replace('\\', '/')
    marker = MOTION + '/'
    if marker not in raw:
        raise ValueError('Water forceRoot is not an identifiable repository path')
    relative = marker + raw.split(marker, 1)[1]
    safe_path(root, relative)
    return relative.rstrip('/')


def required_inputs(root: Path, elements: Sequence[str], native_water: bool) -> list[str]:
    paths: set[str] = set()
    if set(elements) & {'fire', 'air', 'ice', 'lava', 'lightning'}:
        paths.add(SOURCE)
    if set(elements) & {'earth', 'ice', 'lava'}:
        paths.add(GEOMETRY)
    if set(elements) & {'earth', 'lava'}:
        paths.update(TEXTURES + name for name in ('rock_09_diff_2k.jpg', 'rock_09_nor_gl_2k.jpg'))
    if 'earth' in elements:
        paths.add(TEXTURES + 'rock_09_arm_2k.jpg')
    if 'lightning' in elements:
        paths.add(ACTIVE + '/lightning/channels.json')
    if 'water' in elements:
        paths.update(ACTIVE + '/water-full/' + name for name in ('config.json', 'parcels.f32', 'guides.npz'))
        paths.update(force_root(root) + f'/guide-{i}.f32' for i in range(3))
        if not native_water:
            paths.add(PLAYER + '/water-02-r7.mp4')
    return sorted(paths)


def plan(root: Path, elements: Sequence[str], diagnostic: Diagnostic | None, native_water: bool) -> dict[str, Any]:
    return {
        'elements': list(elements), 'profile': 'diagnostic' if diagnostic else 'production',
        'sourceCheckout': str(root), 'writesToSourceCheckout': False,
        'resolution': [diagnostic.width, diagnostic.height] if diagnostic else [1920, 1080],
        'fps': 30, 'gasGrid': [diagnostic.x, diagnostic.y, diagnostic.z] if diagnostic else list(FULL_GRID),
        'gasSubsteps': 3,
        'renderers': {e: ('PyTorch CPU volume integration' if e in ('fire', 'air') else
                         'Eevee through verified Mesa CPU software rasterization' if e == 'lightning' else
                         'Cycles CPU + CPU OpenImageDenoise') for e in elements},
        'expectedFrames': {e: diagnostic.frames if diagnostic else (294 if e in ('fire', 'air') else
                         (240 if native_water else 336) if e == 'water' else 300) for e in elements},
        'waterOpening': 'none; fresh 8-second native segment only' if native_water else
                        'same published edit; first 102 source frames retained from water r7, 6-frame overlap',
        'earthEdit': 'fresh 390-frame CPU render, then original 300-frame reverse-arrival edit',
        'limitations': ['CPU and GPU floating-point trajectories need not be bit-identical',
                        'OpenImageDenoise replaces the OptiX denoiser; final pixels can differ',
                        'Lightning software Eevee requires Linux, Mesa, Xvfb and a successful renderer probe',
                        'No automatic resolution, sample-count, solver-grid or bounce-count downgrade'],
        'requiredInputs': required_inputs(root, elements, native_water),
        'visualAcceptance': 'pending',
    }


def check_dependencies(elements: Sequence[str], blender: str | None, threads: int) -> dict[str, Any]:
    if not 1 <= threads <= 1024:
        raise ValueError('threads must be in 1..1024')
    tools = {'ffmpeg': executable('ffmpeg'), 'ffprobe': executable('ffprobe')}
    modules = {'numpy', 'PIL'}
    if set(elements) & {'fire', 'air'}:
        modules.add('torch')
    if set(elements) & {'ice', 'lava', 'lightning', 'water'}:
        modules.add('scipy')
    if 'water' in elements:
        tools['node'] = executable('node')
        modules.update({'numba', 'skimage'})
    if set(elements) - {'fire', 'air'}:
        tools['blender'] = executable('blender', blender)
    if 'lightning' in elements:
        if platform.system() != 'Linux':
            raise RuntimeError('GPU-free Eevee is supported only on Linux with Mesa/Xvfb; run the other six separately')
        tools['xvfb'] = executable('xvfb-run')
    missing = [module for module in sorted(modules) if importlib.util.find_spec(module) is None]
    if missing:
        raise ImportError('Missing Python dependencies: ' + ', '.join(missing))
    return {'tools': tools, 'python': sys.version, 'platform': platform.platform(),
            'threadsPerWorker': threads, 'modules': sorted(modules)}


def peak_rss_mib(pids: Sequence[int]) -> float | None:
    if platform.system() != 'Linux':
        return None
    total = 0
    for pid in pids:
        try:
            for line in Path(f'/proc/{pid}/status').read_text().splitlines():
                if line.startswith('VmHWM:'):
                    total += int(line.split()[1])
        except (OSError, ValueError):
            pass
    return total / 1024


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == 'posix':
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    else:
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == 'posix':
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.wait()


def run_group(commands: Sequence[tuple[str, list[str]]], output: Path, workspace: Path,
              env: dict[str, str], timeout: float, disk_reserve: int) -> dict[str, Any]:
    """Concurrent producer/consumer group, required for bounded water caches.

    Any child failure terminates peers and descendants. Every process has its own
    log and process group, and a stage deadline prevents indefinite cache waits.
    """
    logs = output / 'logs'
    logs.mkdir(exist_ok=True)
    started = time.monotonic()
    processes: list[tuple[str, subprocess.Popen]] = []
    handles = []
    peak = None
    try:
        for name, command in commands:
            stream = (logs / (name + '.log')).open('xb')
            handles.append(stream)
            options = {'start_new_session': True} if os.name == 'posix' else {
                'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
            process = subprocess.Popen(command, cwd=workspace, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, **options)
            processes.append((name, process))
        while True:
            failures = [(name, p.returncode) for name, p in processes if p.poll() not in (None, 0)]
            if failures:
                raise RuntimeError(f'Stage failed: {failures}; see {logs}')
            if all(p.poll() is not None for _, p in processes):
                break
            if time.monotonic() - started > timeout:
                raise TimeoutError(f'Stage deadline exceeded ({timeout:g}s); logs and partial work retained')
            if shutil.disk_usage(workspace).free < disk_reserve:
                raise OSError('Disk reserve reached; stopped before filling the disk')
            rss = peak_rss_mib([p.pid for _, p in processes])
            if rss is not None:
                peak = max(peak or 0, rss)
            time.sleep(.2)
        return {'commands': [{'name': name, 'argv': argv} for name, argv in commands],
                'elapsedSeconds': time.monotonic() - started,
                'sampledSumOfParentPeakRssMiB': peak, 'returnCodes': {n: p.returncode for n, p in processes}}
    finally:
        for _, process in processes:
            stop_process(process)
        for handle in handles:
            handle.close()


PROBE = '''
import bpy, json, os
from pathlib import Path
s=bpy.context.scene
s.render.engine='BLENDER_EEVEE_NEXT' if os.environ.get('CYBR_PROBE_EEVEE')=='1' else 'CYCLES'
s.cycles.device='CPU'
s.cycles.samples=1
s.render.resolution_x=16;s.render.resolution_y=16;s.render.resolution_percentage=100
if hasattr(s.render,'compositor_device'):s.render.compositor_device='CPU'
bpy.ops.render.render()
row={'version':bpy.app.version_string,'engine':s.render.engine,'cyclesDevice':s.cycles.device}
if s.render.engine=='BLENDER_EEVEE_NEXT':
 import gpu
 row['renderer']=gpu.platform.renderer_get()
 row['vendor']=gpu.platform.vendor_get()
 if not any(n in row['renderer'].lower() for n in ['llvmpipe','softpipe']):
  raise RuntimeError('Not a verified CPU rasterizer: '+repr(row))
Path(os.environ['CYBR_PROBE_REPORT']).write_text(json.dumps(row,indent=2))
'''


class Flow:
    def __init__(self, args: argparse.Namespace, root: Path = ROOT):
        self.args, self.root = args, root.resolve()
        self.elements = selected(args.elements)
        self.diagnostic = Diagnostic(args.frames) if args.command == 'smoke' else None
        if self.diagnostic and set(self.elements) - {'fire', 'air'}:
            raise ValueError('Smoke mode supports fire and air only; use --elements fire air')
        self.output = isolated_output(self.root, args.output)
        self.env = cpu_environment(args.threads)
        self.workspace = self.output / 'workspace'
        self.report: dict[str, Any] = {'schema': 'cybr-elements-cpu/1', 'status': 'preparing', 'stages': [], 'films': {}, 'visualAcceptance': 'pending',
            'workflowHashes': {name: sha256(self.root / 'cpu' / name) for name in ('run.py', 'adapter.py', 'assets.py', 'upstream.json')}}
        self.source_hashes: dict[str, str] = {}
        self.tools: dict[str, str] = {}

    def save(self) -> None:
        atomic_json(self.output / 'receipt.json', self.report)

    def stage(self) -> None:
        info = check_dependencies(self.elements, self.args.blender, self.args.threads)
        self.tools = info['tools']
        self.report['environment'] = info
        self.report['plan'] = plan(self.root, self.elements, self.diagnostic, self.args.native_water)
        self.output.mkdir(parents=True, exist_ok=False)
        self.workspace.mkdir()
        self.save()
        locks = json.loads((self.root / 'cpu/upstream.json').read_text(encoding='utf-8'))['sha256']
        for name in sorted({name for e in self.elements for name in DRIVERS[e]}):
            relative = MOTION + '/' + name
            source = self.root / relative
            digest = sha256(source)
            if locks.get(relative) != digest:
                raise ValueError(f'Upstream source drift: {relative}. Review and update the CPU adapter lock first.')
            self.source_hashes[relative] = digest
            copy_new(source, self.workspace / relative)
        if 'water' in self.elements:
            vendor = 'work/flip-lettering/vendor'
            for folder in ('src', 'tools'):
                base = self.root / vendor / folder
                if not base.is_dir():
                    raise FileNotFoundError(f'Missing native water source directory: {base}')
                for source in base.rglob('*'):
                    if source.suffix not in {'.py', '.js', '.mjs', '.json'} or '__pycache__' in source.parts:
                        continue
                    relative = source.relative_to(self.root).as_posix()
                    self.source_hashes[relative] = sha256(source)
                    copy_new(source, self.workspace / relative)
            package = self.root / vendor / 'package.json'
            if package.is_file():
                relative = package.relative_to(self.root).as_posix()
                self.source_hashes[relative] = sha256(package)
                copy_new(package, self.workspace / relative)
        self.report['inputs'] = restore(self.root, self.workspace,
            self.report['plan']['requiredInputs'], input_cache=self.args.input_cache,
            download=self.args.restore_inputs)
        if 'water' in self.elements:
            path = self.workspace / ACTIVE / 'water-full/config.json'
            config = json.loads(path.read_text())
            original_config = dict(config)
            config['forceRoot'] = str(self.workspace / force_root(self.root))
            config['sourceRoot'] = config['forceRoot']
            atomic_json(path, config)
            self.report['waterPathRebase'] = {'before': original_config, 'after': config}
        for folder in ('sigil-02-v2', 'sigil-02-elements', 'sigil-02-bending-ground',
                       'sigil-02-active-elements'):
            (self.workspace / MOTION / folder).mkdir(parents=True, exist_ok=True)
        for e in self.elements:
            (self.workspace / ACTIVE / e).mkdir(parents=True, exist_ok=True)
        if 'lightning' in self.elements:
            from PIL import Image
            Image.new('RGB', (1920, 1080)).save(self.workspace / ACTIVE / 'black-1080.jpg', quality=97)
        adaptations = []
        for name in sorted({n for e in self.elements for n in DRIVERS[e]} & (GAS | BLENDER | IO_ONLY)):
            path = self.workspace / MOTION / name
            code, receipt = adapt(path.read_text(encoding='utf-8'), name, self.args.threads,
                                  self.diagnostic if name in GAS else None)
            path.write_text(code, encoding='utf-8')
            adaptations.append(receipt)
        if 'water' in self.elements:
            path = self.workspace / MOTION / 'sigil_02_active_water.mjs'
            code, receipt = adapt_javascript_manifest(path.read_text(encoding='utf-8'))
            path.write_text(code, encoding='utf-8')
            adaptations.append(receipt)
        if self.diagnostic:
            self.resample_source()
        # Original telemetry uses zero GPU bytes; avoid an ambiguous zero-memory claim.
        self.report['adaptations'] = adaptations
        self.report['sourceHashesBefore'] = self.source_hashes
        self.report['cudaVisibility'] = self.env['CUDA_VISIBLE_DEVICES']
        self.report['gpuUsed'] = False
        self.report['physicalGpuRequired'] = False
        self.report['diagnosticNotQualityParity'] = self.diagnostic is not None
        self.save()
        if 'blender' in self.tools:
            self.probe_blender()

    def resample_source(self) -> None:
        import numpy as np
        import torch
        import torch.nn.functional as F
        path = self.workspace / SOURCE
        d = self.diagnostic
        assert d is not None
        with np.load(path, allow_pickle=False) as source:
            fields = {key: source[key].copy() for key in source.files}
        before = sha256(path)
        for key in ('support', 'sdf', 'arrival', 'dirx', 'dirz'):
            value = torch.from_numpy(fields[key].astype('float32'))[None, None]
            fields[key] = F.interpolate(value, size=(d.z, d.x), mode='bilinear', align_corners=True)[0, 0].numpy()
        np.savez_compressed(path, **fields)
        self.report['diagnosticSourceResampling'] = {'originalSha256': before, 'resampledSha256': sha256(path),
                                                    'gridXZ': [d.x, d.z], 'productionInputChanged': False}

    def group(self, commands: Sequence[tuple[str, list[str]]]) -> None:
        stage = run_group(commands, self.output, self.workspace, self.env,
                          self.args.timeout, self.args.disk_reserve_mib * 1024**2)
        self.report['stages'].append(stage)
        self.save()

    def blender_command(self, path: Path, args: Sequence[str] = (), software: bool = False) -> list[str]:
        command = [self.tools['blender'], '--background', '--factory-startup',
                   '--python-exit-code', '1', '--threads', str(self.args.threads), '--python', str(path), '--', *args]
        if software:
            command = [self.tools['xvfb'], '-a', '-s', '-screen 0 1920x1080x24', *command]
        return command

    def probe_blender(self) -> None:
        probe = self.workspace / 'cpu-probe.py'
        probe.write_text(PROBE, encoding='utf-8')
        self.report['blenderProbes'] = {}
        for engine in (['cycles', 'eevee'] if 'lightning' in self.elements else ['cycles']):
            result = self.output / (f'blender-{engine}-probe.json')
            self.env['CYBR_PROBE_REPORT'] = str(result)
            self.env['CYBR_PROBE_EEVEE'] = '1' if engine == 'eevee' else '0'
            self.group([(f'blender-{engine}-probe', self.blender_command(probe, software=engine == 'eevee'))])
            row = json.loads(result.read_text())
            version = row['version']
            if not version.startswith('4.5.'):
                raise RuntimeError(f'Blender 4.5 LTS required for these adopted scenes; found {version}')
            if engine == 'eevee':
                renderer = row.get('renderer', '').lower()
                if not any(name in renderer for name in ('llvmpipe', 'softpipe')):
                    raise RuntimeError('Software-renderer verification failed')
                self.env['CYBR_EEVEE_SOFTWARE_VERIFIED'] = '1'
            self.report['blenderProbes'][engine] = row
            self.save()

    def probe_only(self) -> None:
        info = check_dependencies(self.elements, self.args.blender, self.args.threads)
        self.tools = info['tools']
        if 'blender' not in self.tools:
            raise ValueError('probe requires at least one Blender-rendered element')
        self.output.mkdir(parents=True, exist_ok=False)
        self.workspace.mkdir()
        self.report['environment'] = info
        self.save()
        try:
            self.probe_blender()
            self.report['status'] = 'completed-backend-probe'
            self.save()
        except BaseException as exc:
            self.report['status'] = 'failed'
            self.report['error'] = f'{type(exc).__name__}: {exc}'
            self.save()
            raise

    def frames_to_video(self, name: str, directory: Path, output: Path, count: int) -> None:
        existing = sorted(directory.glob('[0-9][0-9][0-9][0-9].jpg'))
        expected = [directory / f'{f:04}.jpg' for f in range(count)]
        if existing != expected:
            raise ValueError(f'Incomplete or extra frame sequence for {name}: {len(existing)} / {count}')
        self.group([(name + '-encode', [self.tools['ffmpeg'], '-v', 'error', '-n', '-threads', str(self.args.threads),
            '-framerate', '30', '-start_number', '0', '-i', str(directory / '%04d.jpg'),
            '-frames:v', str(count), '-an', '-c:v', 'libx264', '-threads', str(self.args.threads),
            '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(output)])])

    def verify_video(self, path: Path, expected_frames: int) -> dict[str, Any]:
        command = [self.tools['ffprobe'], '-v', 'error', '-select_streams', 'v:0', '-count_frames',
                   '-show_entries', 'stream=width,height,avg_frame_rate,nb_read_frames:format=duration',
                   '-of', 'json', str(path)]
        result = subprocess.run(command, env=self.env, capture_output=True, text=True, check=True,
                                timeout=self.args.timeout)
        data = json.loads(result.stdout)
        stream = data['streams'][0]
        width, height = (self.diagnostic.width, self.diagnostic.height) if self.diagnostic else (1920, 1080)
        if (stream['width'], stream['height'], stream['avg_frame_rate'], int(stream['nb_read_frames'])) != (
                width, height, '30/1', expected_frames):
            raise ValueError(f'Unexpected video metadata: {data}')
        self.group([(path.stem + '-decode', [self.tools['ffmpeg'], '-v', 'error', '-xerror',
                    '-threads', str(self.args.threads), '-i', str(path), '-map', '0:v:0', '-f', 'null', '-'])])
        return {'path': str(path.relative_to(self.output)), 'sha256': sha256(path), 'metadata': data,
                'fullyDecoded': True, 'visualAcceptance': 'pending'}

    def render(self, element: str) -> None:
        motion = self.workspace / MOTION
        movies = self.output / 'films'
        movies.mkdir(exist_ok=True)
        destination = movies / (element + '-cpu.mp4')
        if element in ('fire', 'air'):
            d = self.diagnostic
            grid = (d.x, d.y, d.z) if d else FULL_GRID
            command = [sys.executable, str(motion / DRIVERS[element][0]), '--size', *map(str, grid),
                       '--fps', '30', '--substeps', '3', '--name', element + '-cpu']
            self.group([(element + '-simulate-render', command)])
            relative = 'sigil-02-v2/fire-02.mp4' if element == 'fire' else 'sigil-02-elements/air-02-v2.mp4'
            copy_new(motion / relative, destination)
        elif element == 'earth':
            self.group([('earth-render', self.blender_command(motion / DRIVERS[element][0], ['--full']))])
            native = movies / 'earth-native-390.mp4'
            self.frames_to_video('earth', motion / 'sigil-02-bending-ground/earth-frames', native, 390)
            edit = ('[0:v]split[a][b];[a]trim=start_frame=210:end_frame=331,setpts=PTS-STARTPTS,reverse[r];'
                    '[b]trim=start_frame=211:end_frame=390,setpts=PTS-STARTPTS[f];'
                    '[r][f]concat=n=2:v=1:a=0[v]')
            self.edit_video('earth', [native], destination, edit)
        elif element == 'water':
            commands = [
                ('water-solve', [self.tools['node'], str(motion / 'sigil_02_active_water.mjs'), '--full']),
                ('water-mesh', [sys.executable, str(motion / 'sigil_02_active_mesh.py'), '--full']),
                ('water-render', self.blender_command(motion / 'sigil_02_active_water_render.py', ['--full'])),
            ]
            self.group(commands)
            native = movies / 'water-native-240.mp4'
            self.frames_to_video('water', self.workspace / ACTIVE / 'water-full/frames', native, 240)
            if self.args.native_water:
                copy_new(native, destination)
            else:
                edit = ('[0:v]trim=start_frame=0:end_frame=102,setpts=PTS-STARTPTS[a];'
                        '[1:v]setpts=PTS-STARTPTS[b];'
                        '[a][b]xfade=transition=fade:duration=0.20:offset=3.20,format=yuv420p[v]')
                self.edit_video('water', [self.workspace / PLAYER / 'water-02-r7.mp4', native], destination, edit)
        else:
            driver = motion / 'sigil_02_new_materials.py'
            if element in ('ice', 'lava'):
                self.group([(element + '-rigid-solve', self.blender_command(driver, [element, '--full', '--physics-only']))])
            self.group([(element + '-atmosphere', [sys.executable, str(motion / 'sigil_02_atmosphere.py'), element])])
            self.group([(element + '-render', self.blender_command(driver, [element, '--full'], software=element == 'lightning'))])
            self.frames_to_video(element, self.workspace / ACTIVE / element / 'frames', destination, 300)
        frames = self.report['plan']['expectedFrames'][element]
        self.report['films'][element] = self.verify_video(destination, frames)
        if element == 'water':
            self.report['films'][element]['retainedOpening'] = not self.args.native_water
        self.save()
        print(f'CPU film complete and decoded: {destination}', flush=True)

    def edit_video(self, name: str, sources: list[Path], destination: Path, filtergraph: str) -> None:
        command = [self.tools['ffmpeg'], '-v', 'error', '-n']
        for source in sources:
            command += ['-threads', str(self.args.threads), '-i', str(source)]
        command += ['-filter_complex_threads', str(self.args.threads), '-filter_complex', filtergraph,
                    '-map', '[v]', '-an', '-c:v', 'libx264', '-threads', str(self.args.threads),
                    '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(destination)]
        self.group([(name + '-edit', command)])

    def verify_source(self) -> None:
        changed = [path for path, digest in self.source_hashes.items() if sha256(self.root / path) != digest]
        self.report['sourceFilesUnchanged'] = not changed
        if changed:
            raise RuntimeError('Source checkout changed during execution: ' + ', '.join(changed))

    def player(self) -> None:
        cards = []
        for element, film in self.report['films'].items():
            cards.append(f'<section><h2>{html.escape(element.title())}</h2><video controls loop playsinline preload="metadata" '
                         f'src="{html.escape(film["path"], quote=True)}"></video></section>')
        label = 'DIAGNOSTIC — reduced grid, not production visual parity' if self.diagnostic else 'CPU production candidates — visual review pending'
        page = ('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>CYBR ELEMENTS / CPU</title><style>body{background:#080a0e;color:#eef0f6;font:17px system-ui;'
                'max-width:1200px;margin:auto;padding:24px}video{width:100%;background:black}section{margin:32px 0}'
                'a{color:#b6d6ff}p{line-height:1.6}</style><h1>CYBR ELEMENTS / CPU</h1>'
                f'<p>{label}. Original films and player are unchanged.</p>'
                '<p><a href="receipt.json">Execution receipt, sources, backend and validation</a></p>' + ''.join(cards))
        (self.output / 'index.html').write_text(page, encoding='utf-8')

    def run(self) -> None:
        try:
            self.stage()
            self.report['status'] = 'running'
            self.save()
            for element in self.elements:
                self.render(element)
            self.verify_source()
            self.report['status'] = 'completed-diagnostic' if self.diagnostic else 'completed-awaiting-visual-review'
            self.player()
            self.save()
        except BaseException as exc:
            if self.output.is_dir():
                self.report['status'] = 'failed'
                self.report['error'] = f'{type(exc).__name__}: {exc}'
                self.save()
            raise


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('plan', 'doctor', 'probe', 'run', 'smoke'))
    p.add_argument('--elements', nargs='+', default=['all'], choices=(*ELEMENTS, 'all'))
    p.add_argument('--output', type=Path, help='A NEW directory outside the checkout')
    p.add_argument('--input-cache', type=lambda s: Path(s).expanduser().resolve(), help='Read-only mirror of original asset paths')
    p.add_argument('--restore-inputs', action='store_true', help='Download missing, checksummed release inputs into the workspace')
    p.add_argument('--blender', help='Blender 4.5 LTS executable; defaults to PATH')
    p.add_argument('--threads', type=int, default=2, help='Per-worker CPU thread budget; water uses concurrent workers')
    p.add_argument('--timeout', type=float, default=604800, help='Maximum seconds per stage, including water worker group (default 7 days)')
    p.add_argument('--disk-reserve-mib', type=int, default=1024)
    p.add_argument('--native-water', action='store_true', help='Produce only the fresh 8s water segment; do not reuse the historical opening')
    p.add_argument('--frames', type=int, default=72, help='Smoke mode only: explicit diagnostic length, 1..294')
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        elements = selected(args.elements)
        if args.timeout <= 0 or args.disk_reserve_mib < 0:
            raise ValueError('timeout must be positive and disk reserve nonnegative')
        if args.command == 'plan':
            print(json.dumps(plan(ROOT, elements, None, args.native_water), indent=2))
        elif args.command == 'doctor':
            print(json.dumps(check_dependencies(elements, args.blender, args.threads), indent=2))
        else:
            if args.output is None:
                raise ValueError('--output is required; existing directories are never reused')
            flow = Flow(args)
            flow.probe_only() if args.command == 'probe' else flow.run()
        return 0
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as exc:
        print(f'CPU workflow stopped: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
