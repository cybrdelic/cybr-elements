#!/usr/bin/env python3
"""Run the checked-in fire/air solvers on CPU without editing their sources.

The original pressure projection, limited MacCormack transport, source,
reaction, vorticity and volume optics are executed directly from their source.
CPU execution also omits channels overwritten before any consumer and factors
the Cartesian max limiter into equivalent one-dimensional passes. These
changes retain the original state exactly in paired solver checks. The source SDF is resampled to the selected grid;
no existing film or baked simulation frame is read.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

import numpy as np
from PIL import Image
from scipy.ndimage import binary_fill_holes, label, map_coordinates



class CPUFunctional:
    def __init__(self):
        import torch.nn.functional as native
        self.native = native

    def __getattr__(self, name):
        return getattr(self.native, name)

    def max_pool3d(self, value, kernel_size, stride=None, padding=0, **kwargs):
        if kernel_size == 3 and stride == 1 and padding == 1 and not kwargs:
            result = self.native.max_pool3d(value, (1, 1, 3), stride=1, padding=(0, 0, 1))
            result = self.native.max_pool3d(result, (1, 3, 1), stride=1, padding=(0, 1, 0))
            return self.native.max_pool3d(result, (3, 1, 1), stride=1, padding=(1, 0, 0))
        return self.native.max_pool3d(value, kernel_size, stride=stride, padding=padding, **kwargs)


def specialize_transport(kind, original_step):
    start = original_step.index('    vel=state[:,:3]\n')
    end = original_step.index('    fuel,oxygen,temp,soot=', start)
    if kind == 'fire':
        block = '''    vel=state[:,:3]
    moved7=advect(state[:,:7],vel)
    returned=advect(moved7[:,3:7],vel,-1)
    corrected=moved7[:,3:7]+.5*(state[:,3:7]-returned)
    upper=F.max_pool3d(state[:,3:7],3,stride=1,padding=1)
    lower=-F.max_pool3d(-state[:,3:7],3,stride=1,padding=1)
    departure=grid-(vel*step_scale*dt).permute(0,2,3,4,1)
    upper=F.grid_sample(upper,departure,mode='nearest',padding_mode='border',align_corners=True)
    lower=F.grid_sample(lower,departure,mode='nearest',padding_mode='border',align_corners=True)
    moved7[:,3:7]=torch.maximum(lower,torch.minimum(upper,corrected)).clamp_min_(0)
    moved=torch.cat((moved7,state[:,7:8]),dim=1)
    state=moved
    del vel,returned,corrected,upper,lower,departure,moved,moved7
'''
    elif kind == 'air':
        block = '''    vel=state[:,:3]
    packed=torch.cat((state[:,:3],state[:,6:7]),dim=1)
    moved4=advect(packed,vel)
    returned=advect(moved4[:,3:4],vel,-1)
    corrected=moved4[:,3:4]+.5*(state[:,6:7]-returned)
    upper=F.max_pool3d(state[:,6:7],3,stride=1,padding=1)
    lower=-F.max_pool3d(-state[:,6:7],3,stride=1,padding=1)
    departure=grid-(vel*step_scale*dt).permute(0,2,3,4,1)
    upper=F.grid_sample(upper,departure,mode='nearest',padding_mode='border',align_corners=True)
    lower=F.grid_sample(lower,departure,mode='nearest',padding_mode='border',align_corners=True)
    moved4[:,3:4]=torch.maximum(lower,torch.minimum(upper,corrected)).clamp_min_(0)
    moved=state.clone()
    moved[:,:3]=moved4[:,:3]
    moved[:,6:7]=moved4[:,3:4]
    state=moved
    del vel,returned,corrected,upper,lower,departure,moved,packed,moved4
'''
    else:
        raise ValueError(kind)
    optimized = original_step[:start] + block + original_step[end:]
    assert optimized[optimized.index('    fuel,oxygen,temp,soot='):] == original_step[end:]
    return optimized


def install_cpu_operators(namespace, kind, original_step, *, specialize=True):
    namespace['F'] = CPUFunctional()
    step = specialize_transport(kind, original_step) if specialize else original_step
    exec(compile(step, f'<cpu-{kind}-transport>', 'exec'), namespace)
    return {'separable_pool': True, 'dead_channel_transport_omitted': specialize,
            'executed_step_sha256': hashlib.sha256(step.encode()).hexdigest()}

def arguments():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind', choices=['fire', 'air'], required=True)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--source', type=Path, help='Approved artwork-derived source NPZ; defaults to the repository source asset')
    p.add_argument('--output', type=Path, help='Output directory; defaults to work/cpu-renders/<element>')
    p.add_argument('--grid', type=int, nargs=3, default=[320, 32, 180], metavar=('X', 'Y', 'Z'))
    p.add_argument('--resolution', type=int, nargs=2, default=[1280, 720], metavar=('WIDTH', 'HEIGHT'))
    p.add_argument('--fps', type=int, default=30)
    p.add_argument('--frames', type=int, default=294)
    p.add_argument('--substeps', type=int, default=3)
    p.add_argument('--threads', type=int, default=6)
    p.add_argument('--benchmark', action='store_true', help='Compute/render actual frames without launching video encoder')
    p.add_argument('--save-every', type=int, default=30)
    p.add_argument('--native-transport', action='store_true', help='Retain all original transported channels for equivalence audits')
    a = p.parse_args()
    a.repo = a.repo.expanduser().resolve()
    a.source = (a.source or a.repo / 'work/element-motion/sigil-02-v2/source.npz').expanduser().resolve()
    a.output = (a.output or a.repo / 'work/cpu-renders' / a.kind).expanduser().resolve()
    if min(a.grid) < 8 or min(a.resolution) < 32 or a.fps < 1 or a.frames < 1 or a.substeps < 1 or a.threads < 1 or a.save_every < 1:
        p.error('Dimensions and sampling counts must be positive and sufficiently large')
    if a.resolution[0] % 2 or a.resolution[1] % 2:
        p.error('H.264 output dimensions must be even')
    if np.prod(a.grid) > 7_000_000:
        p.error('This bounded-memory CPU wrapper permits at most seven million cells')
    return a


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def field_topology(binary):
    structure = np.ones((3, 3), np.uint8)
    return {'components': int(label(binary, structure=structure)[1]),
            'holes': int(label(binary_fill_holes(binary) & ~binary, structure=structure)[1])}


def resample_source(a, destination):
    if destination.resolve() == a.source.resolve():
        raise ValueError('Output must not overwrite the original source NPZ')
    original_checksum = checksum(a.source)
    x, _, z = a.grid
    with np.load(a.source, allow_pickle=False) as original:
        required = ('support', 'sdf', 'arrival', 'dirx', 'dirz', 'lo', 'extent')
        if any(name not in original for name in required):
            raise ValueError('Source NPZ is missing an emitter field')
        if any(not np.isfinite(original[name]).all() for name in required):
            raise ValueError('Source NPZ contains nonfinite data')
        if original['sdf'].ndim != 2 or any(original[name].shape != original['sdf'].shape for name in required[:5]):
            raise ValueError('Source fields must have the same two-dimensional grid')
        if not np.allclose(original['lo'], [-7., -.6, -1.05]) or not np.allclose(original['extent'], [14., 1.2, 7.875]):
            raise ValueError('Source bounds differ from the solver camera contract')
        original_z, original_x = original['sdf'].shape
        rows, columns = np.meshgrid(np.linspace(0, original_z - 1, z),
                                    np.linspace(0, original_x - 1, x), indexing='ij')
        coordinates = np.stack([rows, columns])
        fields = {name: map_coordinates(original[name], coordinates, order=1, mode='nearest').astype(np.float32)
                  for name in ['sdf', 'arrival', 'dirx', 'dirz']}
        fields['lo'] = original['lo'].copy()
        fields['extent'] = original['extent'].copy()
        spacing = float(fields['extent'][0]) / (x - 1)
        fields['support'] = np.clip(fields['sdf'] / spacing + .5, 0, 1).astype(np.float32)
        magnitude = np.hypot(fields['dirx'], fields['dirz']).clip(min=1e-8)
        fields['dirx'] /= magnitude
        fields['dirz'] /= magnitude
        original_topology = field_topology(original['support'] > .5)
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(destination, **fields)
    preview = (np.flipud(fields['support']) * 255).astype(np.uint8)
    Image.fromarray(preview).resize((1280, 720), Image.Resampling.LANCZOS).save(a.output / 'source-support.png')
    return {'original_grid': [original_x, original_z], 'resampled_grid': [x, z],
            'original_topology': original_topology, 'resampled_topology': field_topology(fields['support'] > .5),
            'sha256_original': original_checksum, 'sha256_resampled': checksum(destination)}


def source_function(text, name):
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(text, node)


def load_solver(a):
    import torch
    path = a.repo / 'work/element-motion' / f'sigil_02_{a.kind}_v2.py'
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    encoder_import = next(node for node in tree.body if isinstance(node, ast.Import) and
                          any(alias.name == 'subprocess' for alias in node.names))
    prefix = '\n'.join(source.splitlines()[:encoder_import.lineno - 1]) + '\n'
    cuda_guard = "if not torch.cuda.is_available(): raise RuntimeError('CUDA is required for this offline bake')"
    if prefix.count(cuda_guard) != 1 or prefix.count("device='cuda'") != 1:
        raise RuntimeError('Expected checked-in device initialization; source structure changed')
    prefix = prefix.replace(cuda_guard, '# CPU portability: the same torch operators run on CPU.')
    prefix = prefix.replace("device='cuda'", "device='cpu'")
    prefix = prefix.replace('torch.set_num_threads(2)', f'torch.set_num_threads({a.threads})')
    if "torch.cuda" in prefix:
        raise RuntimeError('An unexpected CUDA-only call remains in the initialization')
    namespace = {'__file__': str(a.output / path.name), '__name__': '__portable_solver__'}
    previous_argv = sys.argv
    try:
        sys.argv = [str(path), '--size', *map(str, a.grid), '--fps', str(a.fps), '--substeps', str(a.substeps),
                    '--name', f'cpu-{a.kind}']
        exec(compile(prefix, str(path), 'exec'), namespace)
    finally:
        sys.argv = previous_argv
    render_source = source_function(source, 'render')
    if render_source.count('size=(1080,1920)') != 1:
        raise RuntimeError('Expected original full-frame optical integration')
    render_source = render_source.replace('size=(1080,1920)', f'size=({a.resolution[1]},{a.resolution[0]})')
    render_source = render_source.replace('if frame%5==0 or frame==TOTAL-1:', f'if frame%{a.save_every}==0 or frame==135 or frame==TOTAL-1:')
    if source_function(prefix, 'step') != source_function(source, 'step'):
        raise RuntimeError('Numerical step was changed by portability adaptation')
    namespace.update(FPS=a.fps, SIM_FPS=a.fps, TOTAL=a.frames, W=a.resolution[0], H=a.resolution[1])
    exec(compile(render_source, f'{path}:portable-render', 'exec'), namespace)
    execution_metadata = install_cpu_operators(namespace, a.kind, source_function(source, 'step'), specialize=not a.native_transport)
    evidence = {'adapter_sha256': checksum(Path(__file__).resolve()), 'solver_file': str(path), 'solver_sha256': checksum(path),
                'original_step_sha256': hashlib.sha256(source_function(source, 'step').encode()).hexdigest(),
                'original_radiance_sha256': hashlib.sha256(source_function(source, 'radiance').encode()).hexdigest(),
                'original_render_sha256': hashlib.sha256(source_function(source, 'render').encode()).hexdigest(),
                'torch_version': torch.__version__, 'cpu_execution': execution_metadata}
    return namespace, evidence


class BenchmarkEncoder:
    def __init__(self):
        self.stdin = self
        self.byte_count = 0

    def write(self, data):
        self.byte_count += len(data)
        return len(data)


def main():
    a = arguments()
    a.output.mkdir(parents=True, exist_ok=True)
    source_metadata = resample_source(a, a.output / 'sigil-02-v2/source.npz')
    os.environ['OMP_NUM_THREADS'] = str(a.threads)
    os.environ['MKL_NUM_THREADS'] = str(a.threads)
    import torch
    torch.set_grad_enabled(False)
    namespace, evidence = load_solver(a)
    video_path = a.output / f'{a.kind}-02-cpu.mp4'
    if a.benchmark:
        encoder = BenchmarkEncoder()
    else:
        encoder = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo',
                                    '-pix_fmt', 'rgb24', '-s', f'{a.resolution[0]}x{a.resolution[1]}', '-r', str(a.fps),
                                    '-i', '-', '-an', '-c:v', 'libx264', '-threads', '1', '-preset', 'fast', '-crf', '17',
                                    '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(video_path)], stdin=subprocess.PIPE)
    namespace['encoder'] = encoder
    rows = []
    start = time.monotonic()
    try:
        for frame in range(a.frames):
            begin = time.monotonic()
            for sub in range(a.substeps):
                divergence = namespace['step']((frame + sub / a.substeps) / a.fps)
            state = namespace['state']
            if not bool(torch.isfinite(state).all()):
                raise RuntimeError(f'Nonfinite simulation state at frame {frame}')
            namespace['render'](frame)
            row = {'frame': frame, 'simulation_time': (frame + 1) / a.fps, 'wall_seconds': time.monotonic() - begin,
                   'divergence_rms': divergence, 'fuel_sum': float(state[0, 3].sum()),
                   'soot_sum': float(state[0, 6].sum()), 'reaction_sum': float(state[0, 7].sum()),
                   'peak_ram_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}
            rows.append(row)
            if a.benchmark or frame % a.fps == 0:
                print(json.dumps(row), flush=True)
            if frame % 30 == 0:
                (a.output / 'progress.json').write_text(json.dumps({'completed_frames': frame + 1, 'target_frames': a.frames,
                                                                  'elapsed_seconds': time.monotonic() - start, 'last_frame': row}, indent=2))
    finally:
        if not a.benchmark:
            encoder.stdin.close()
            if encoder.wait() != 0:
                raise RuntimeError('Video encoder failed')
    elapsed = time.monotonic() - start
    useful_rows = rows[2:] if len(rows) > 3 else rows
    median_frame = float(np.median([r['wall_seconds'] for r in useful_rows]))
    settings = {'element': a.kind, 'grid_xyz': a.grid, 'resolution': a.resolution, 'fps': a.fps,
                'frames': a.frames, 'substeps': a.substeps, 'threads': a.threads,
                'cpu_execution': evidence['cpu_execution'], 'flush_denormal': False}
    settings_hash = hashlib.sha256(json.dumps(settings, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    report = {'settings': settings, 'settings_sha256': settings_hash, 'element': a.kind, 'benchmark': a.benchmark, 'frames': a.frames, 'fps': a.fps,
              'duration_seconds': a.frames / a.fps, 'output_resolution': a.resolution, 'solver_grid_xyz': a.grid,
              'substeps': a.substeps, 'threads': a.threads, 'elapsed_seconds': elapsed,
              'median_frame_seconds_after_warmup': median_frame,
              'estimated_294_frame_seconds': median_frame * 294,
              'peak_ram_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
              'device': 'cpu', 'source': source_metadata, 'solver_evidence': evidence,
              'frame_metrics': rows, 'video': str(video_path) if not a.benchmark else None}
    (a.output / 'render-report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k not in ['frame_metrics', 'solver_evidence', 'source']}), flush=True)


if __name__ == '__main__':
    main()
