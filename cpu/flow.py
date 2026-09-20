#!/usr/bin/env python3
"""An additive, isolated CPU execution path for the existing CYBR Elements sources.

Nothing in work/, outputs/, or the existing GPU pipeline is edited in the source
checkout. Production gas functions are extracted from the original AST, not
reimplemented. Blender scenes are forced onto CPU Cycles before every render.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ELEMENTS = Path('work/element-motion')
ART = Path('outputs/cybrdelic-type/exploration-v6/cybrdelic-brandmark-refined.png')
GAS_GRID = (896, 56, 504)
PROTECTED_FUNCTIONS = ('advect', 'derivative', 'divergence', 'step', 'radiance', 'render')
EXCLUDED = {'.git', '__pycache__', '.pytest_cache', '.asset-downloads', 'node_modules'}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.partial')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def cpu_environment(threads: int) -> dict[str, str]:
    if threads < 1:
        raise ValueError('threads must be positive')
    env = dict(os.environ)
    env.update(CUDA_VISIBLE_DEVICES='', HIP_VISIBLE_DEVICES='', ROCR_VISIBLE_DEVICES='',
               NVIDIA_VISIBLE_DEVICES='void', ONEAPI_DEVICE_SELECTOR='*:cpu',
               OMP_NUM_THREADS=str(threads), MKL_NUM_THREADS=str(threads),
               OPENBLAS_NUM_THREADS=str(threads), NUMEXPR_NUM_THREADS=str(threads),
               PYTHONDONTWRITEBYTECODE='1')
    return env


def executable(name: str) -> str:
    value = shutil.which(name)
    if not value:
        raise RuntimeError(f'Required executable not found: {name}')
    return value


def files_under(root: Path):
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED)
        for directory in dirs:
            if (Path(base) / directory).is_symlink():
                raise RuntimeError(f'Symlink not allowed in isolated workspace: {Path(base) / directory}')
        for name in sorted(files):
            path = Path(base) / name
            if path.is_symlink():
                raise RuntimeError(f'Symlink not allowed in isolated workspace: {path}')
            if path.is_file():
                yield path


def rebase_json(value: Any, destination: Path) -> Any:
    if isinstance(value, dict):
        return {key: rebase_json(item, destination) for key, item in value.items()}
    if isinstance(value, list):
        return [rebase_json(item, destination) for item in value]
    if isinstance(value, str):
        normalized = value.replace('\\', '/')
        # Only absolute archived project paths, not URLs, labels or arbitrary text.
        if '://' not in normalized and (re.match(r'^[A-Za-z]:/', normalized) or normalized.startswith('/')):
            match = re.search(r'/(work|outputs|scripts)/(.+)$', normalized)
            if match:
                relative = Path(match.group(1)) / match.group(2)
                if '..' in relative.parts:
                    raise ValueError(f'Unsafe archived path: {value}')
                return str(destination / relative)
    return value


def stage(source: Path, destination: Path) -> dict[str, Any]:
    source, destination = source.resolve(), destination.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('CPU workspace must be outside and independent of the source checkout')
    if destination.exists():
        raise FileExistsError(f'Refusing to overwrite an existing workspace: {destination}')
    entries = list(files_under(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    needed = sum(path.stat().st_size for path in entries)
    if shutil.disk_usage(destination.parent).free < needed + 2**30:
        raise RuntimeError('Not enough space to copy inputs and retain a 1 GiB reserve')
    destination.mkdir()
    hashes = {}
    for path in entries:
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        # Deliberately copy bytes: never hardlink or symlink to the original.
        shutil.copy2(path, target)
        hashes[relative.as_posix()] = sha(path)
        if sha(target) != hashes[relative.as_posix()]:
            raise RuntimeError(f'Source changed while copying {relative}')
    rebased = []
    for path in (destination / 'work').rglob('*.json'):
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
        except (UnicodeError, json.JSONDecodeError):
            continue
        updated = rebase_json(value, destination)
        if updated != value:
            write_json(path, updated)
            rebased.append(str(path.relative_to(destination)))
    receipt = {'schema': 1, 'source': str(source), 'workspace': str(destination),
               'sourceHashes': hashes, 'rebasedConfigPaths': rebased,
               'copyMethod': 'independent byte copies', 'createdUnix': time.time()}
    write_json(destination / 'cpu-workspace.json', receipt)
    return receipt


def verify_original(workspace: Path) -> dict[str, Any]:
    receipt = json.loads((workspace / 'cpu-workspace.json').read_text())
    source = Path(receipt['source'])
    changed = [name for name, digest in receipt['sourceHashes'].items()
               if not (source / name).is_file() or sha(source / name) != digest]
    result = {'originalFilesChecked': len(receipt['sourceHashes']), 'changed': changed,
              'unchanged': not changed}
    write_json(workspace / 'cpu-original-integrity.json', result)
    if changed:
        raise RuntimeError(f'Original checkout changed during the run: {changed[:10]}')
    return result


def function_hashes(tree: ast.Module) -> dict[str, str]:
    return {node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
            for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in PROTECTED_FUNCTIONS}


class CPUAdapter(ast.NodeTransformer):
    """Change hardware selection, never numerical constants or material values."""
    def __init__(self, threads: int = 2):
        self.threads = threads
        self.edits: list[dict[str, Any]] = []

    def log(self, node: ast.AST, change: str) -> None:
        self.edits.append({'line': getattr(node, 'lineno', None), 'change': change})

    def visit_If(self, node: ast.If):
        text = ast.unparse(node.test)
        if text == 'not torch.cuda.is_available()':
            if len(node.body) != 1 or not isinstance(node.body[0], ast.Raise) or node.orelse:
                raise RuntimeError('Unrecognized CUDA guard; refusing a broad automatic rewrite')
            self.log(node, 'remove CUDA-required abort in CPU execution only')
            return ast.copy_location(ast.Pass(), node)
        return self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        names = [ast.unparse(target) for target in node.targets]
        for name in names:
            if name == 'device' and isinstance(node.value, ast.Constant) and str(node.value.value).startswith('cuda'):
                node.value = ast.Constant('cpu')
                self.log(node, 'PyTorch device=cpu')
            elif name.endswith('.cycles.device'):
                node.value = ast.Constant('CPU')
                self.log(node, 'Cycles CPU')
            elif name.endswith('.compute_device_type'):
                node.value = ast.Constant('NONE')
                self.log(node, 'disable GPU compute backend')
            elif name.endswith('.cycles.denoiser'):
                node.value = ast.Constant('OPENIMAGEDENOISE')
                self.log(node, 'CPU OpenImageDenoise')
            elif name.endswith('.render.engine'):
                node.value = ast.Constant('CYCLES')
                self.log(node, 'CPU Cycles instead of GPU-only engines')
            elif name.endswith('.use') and isinstance(node.value, ast.Compare):
                if any(isinstance(item, ast.Constant) and item.value in ('CUDA', 'OPTIX', 'HIP', 'METAL')
                       for item in node.value.comparators):
                    node.value.comparators = [ast.Constant('CPU')]
                    self.log(node, 'select CPU device only')
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        name = ast.unparse(node.func)
        if name == 'torch.set_num_threads':
            node.args = [ast.Constant(self.threads)]
            self.log(node, 'explicit CPU thread budget')
        elif name in ('torch.cuda.max_memory_allocated', 'torch.cuda.memory_allocated'):
            self.log(node, 'remove GPU-only telemetry')
            return ast.copy_location(ast.Constant(0), node)
        elif name in ('torch.cuda.synchronize', 'torch.cuda.empty_cache'):
            self.log(node, 'remove GPU-only synchronization')
            return ast.copy_location(ast.Constant(None), node)
        elif name == 'bpy.ops.render.render':
            node.func = ast.Name('_cpu_render', ast.Load())
            self.log(node, 'enforce CPU immediately before rendering')
        return self.generic_visit(node)


def gas_program(source: str, threads: int = 2, preview_size: tuple[int, int] | None = None):
    """Extract the existing initialization, solver and renderer, not its GPU queue."""
    original = ast.parse(source)
    prefix = []
    for node in original.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'FPS'
                                               for target in node.targets):
            break
        prefix.append(copy.deepcopy(node))
    else:
        raise RuntimeError('Unsupported gas source: missing production FPS boundary')
    renderer = next((copy.deepcopy(node) for node in original.body
                     if isinstance(node, ast.FunctionDef) and node.name == 'render'), None)
    if renderer is None:
        raise RuntimeError('Unsupported gas source: render() not found')
    tree = ast.Module(body=prefix + [renderer], type_ignores=[])
    adapter = CPUAdapter(threads)
    tree = adapter.visit(tree)
    baseline = function_hashes(original)
    adapted = function_hashes(tree)
    for name in PROTECTED_FUNCTIONS:
        if name in baseline and baseline[name] != adapted.get(name):
            raise RuntimeError(f'CPU adapter changed protected production function: {name}')
    if preview_size:
        class Resize(ast.NodeTransformer):
            def visit_Call(self, node):
                if ast.unparse(node.func) == 'F.interpolate':
                    for item in node.keywords:
                        if item.arg == 'size' and ast.unparse(item.value) == '(1080, 1920)':
                            item.value = ast.Tuple([ast.Constant(preview_size[1]), ast.Constant(preview_size[0])], ast.Load())
                return self.generic_visit(node)
        tree.body[-1] = Resize().visit(tree.body[-1])
    ast.fix_missing_locations(tree)
    remaining = [ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and ast.unparse(node.func).startswith('torch.cuda.')]
    if remaining:
        raise RuntimeError(f'Unadapted CUDA calls: {remaining}')
    return compile(tree, '<existing-cybr-elements-cpu>', 'exec'), {
        'hardwareEdits': adapter.edits, 'productionFunctionHashes': baseline,
        'productionFunctionsIdenticalBeforeExplicitPreviewResize': True,
        'previewResize': list(preview_size) if preview_size else None}


def run_process(command: list[str], cwd: Path, threads: int, log: Path, timeout: float | None = None) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w', encoding='utf-8') as output:
        result = subprocess.run(command, cwd=cwd, env=cpu_environment(threads),
                                stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        tail = log.read_text(encoding='utf-8', errors='replace')[-5000:]
        raise RuntimeError(f'Command failed ({result.returncode}); log: {log}\n{tail}')


def ensure_source(workspace: Path, threads: int) -> None:
    art = workspace / ART
    if not art.is_file():
        raise FileNotFoundError(f'Original artwork is required: {art}. Restore retained assets in the CPU workspace first; no substitute artwork is generated.')
    run_process([sys.executable, str(workspace / ELEMENTS / 'sigil_02_source.py'), 'sigil-02-v2'],
                workspace, threads, workspace / 'cpu-logs/source.log')


def decode_video(path: Path, expected: int, width: int, height: int) -> dict[str, Any]:
    probe = subprocess.run([executable('ffprobe'), '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                            '-show_entries', 'stream=width,height,nb_read_frames,r_frame_rate', '-of', 'json', str(path)],
                           capture_output=True, text=True, check=True)
    stream = json.loads(probe.stdout)['streams'][0]
    actual = (int(stream['nb_read_frames']), stream['width'], stream['height'])
    if actual != (expected, width, height):
        raise RuntimeError(f'Video verification failed: {actual} != {(expected, width, height)}')
    subprocess.run([executable('ffmpeg'), '-v', 'error', '-xerror', '-i', str(path), '-f', 'null', '-'], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return {'decodedFrames': expected, 'width': width, 'height': height, 'sha256': sha(path)}


def run_gas(workspace: Path, material: str, profile: str, threads: int, frames: int | None,
            substeps: int, save_state: bool) -> dict[str, Any]:
    os.environ.update(cpu_environment(threads))
    import numpy as np
    import torch
    import torch.nn.functional as F
    torch.set_num_threads(threads)
    torch.set_grad_enabled(False)
    torch.manual_seed(91351)
    ensure_source(workspace, threads)
    diagnostic = profile == 'smoke'
    size = (128, 24, 72) if diagnostic else GAS_GRID
    width, height = (640, 360) if diagnostic else (1920, 1080)
    count = frames if frames is not None else (30 if diagnostic else 294)
    if count < 1 or count > 294 or substeps < 1:
        raise ValueError('frames must be 1..294; substeps must be positive')
    if diagnostic:
        path = workspace / ELEMENTS / 'sigil-02-v2/source.npz'
        with np.load(path) as original:
            arrays = {key: original[key].copy() for key in original.files}
        for key in ('support', 'sdf', 'arrival', 'dirx', 'dirz'):
            data = torch.from_numpy(arrays[key]).float()[None, None]
            arrays[key] = F.interpolate(data, size=(size[2], size[0]), mode='bilinear', align_corners=True)[0, 0].numpy()
        np.savez_compressed(path, **arrays)
    script = workspace / ELEMENTS / f'sigil_02_{material}_v2.py'
    code, provenance = gas_program(script.read_text(encoding='utf-8'), threads,
                                   (width, height) if diagnostic else None)
    output = workspace / 'cpu-results' / material
    output.mkdir(parents=True, exist_ok=False)
    video = output / f'{material}-{profile}.mp4'
    # Existing legacy completion receipts are not treated as a fresh CPU bake.
    legacy = workspace / ELEMENTS / ('sigil-02-v2/fire-frames' if material == 'fire'
                                     else 'sigil-02-elements/air-frames-v2')
    if legacy.exists():
        shutil.rmtree(legacy)
    old_argv = sys.argv[:]
    namespace = {'__name__': '__cybr_cpu_gas__', '__file__': str(script)}
    begun = time.monotonic()
    try:
        sys.argv = [str(script), '--size', *map(str, size), '--fps', '30', '--substeps', str(substeps)]
        exec(code, namespace)
    finally:
        sys.argv = old_argv
    if namespace['state'].device.type != 'cpu':
        raise RuntimeError('CPU-only contract violated')
    namespace.update(out=output, FPS=30, SIM_FPS=30, TOTAL=count, W=width, H=height)
    command = [executable('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-n', '-f', 'rawvideo',
               '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', '30', '-i', '-', '-an',
               '-c:v', 'libx264', '-threads', str(threads), '-preset', 'fast', '-crf', '17',
               '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(video)]
    rows = []
    with (output / 'encoder.log').open('wb') as errors:
        encoder = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors,
                                   env=cpu_environment(threads))
        namespace['encoder'] = encoder
        try:
            for frame in range(count):
                for sub in range(substeps):
                    divergence = namespace['step']((frame + sub / substeps) / 30)
                state = namespace['state']
                if state.device.type != 'cpu' or not bool(torch.isfinite(state).all()) or not math.isfinite(divergence):
                    raise RuntimeError(f'Invalid CPU simulation state at frame {frame}')
                namespace['render'](frame)
                if frame % 5 == 0 or frame == count - 1:
                    row = {'frame': frame, 'divergenceRMS': divergence,
                           'elapsedSeconds': time.monotonic() - begun, 'device': str(state.device)}
                    rows.append(row)
                    print(json.dumps(row), flush=True)
            encoder.stdin.close()
            if encoder.wait() != 0:
                raise RuntimeError(f'FFmpeg failed; see {output / "encoder.log"}')
        except BaseException:
            encoder.kill()
            encoder.wait()
            if encoder.stdin and not encoder.stdin.closed:
                encoder.stdin.close()
            raise
    validation = decode_video(video, count, width, height)
    if save_state:
        np.savez_compressed(output / 'final-state.npz', state=namespace['state'].cpu().numpy())
    receipt = {'schema': 1, 'material': material, 'profile': profile, 'device': 'cpu',
               'grid': list(size), 'fps': 30, 'frames': count, 'substeps': substeps,
               'sourceSha256': sha(script), 'artworkSha256': sha(workspace / ART),
               'productionQualitySettings': not diagnostic, 'completeProductionDuration': count == 294,
               'visualParityVerified': False, 'humanReviewed': False,
               'reviewQueue': 'Legacy interactive queue replaced by explicit finite CPU loop; no approval receipt fabricated.',
               'torchVersion': torch.__version__, 'elapsedSeconds': time.monotonic() - begun,
               'validation': validation, 'provenance': provenance, 'rows': rows}
    write_json(output / 'receipt.json', receipt)
    return receipt


def force_cycles_cpu(bpy: Any) -> None:
    for scene in bpy.data.scenes:
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'
        if hasattr(scene.cycles, 'denoising_use_gpu'):
            scene.cycles.denoising_use_gpu = False
        if hasattr(scene.render, 'compositor_device'):
            scene.render.compositor_device = 'CPU'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'NONE'
    for device in prefs.devices:
        device.use = device.type == 'CPU'


def blender_worker(script: Path, script_args: list[str], threads: int) -> None:
    import bpy
    adapter = CPUAdapter(threads)
    tree = adapter.visit(ast.parse(script.read_text(encoding='utf-8')))
    ast.fix_missing_locations(tree)
    original_render = bpy.ops.render.render
    render_count = 0
    def cpu_render(*args, **kwargs):
        nonlocal render_count
        force_cycles_cpu(bpy)
        render_count += 1
        return original_render(*args, **kwargs)
    namespace = {'__name__': '__main__', '__file__': str(script), '_cpu_render': cpu_render}
    old_argv = sys.argv[:]
    old_path = sys.path[:]
    try:
        sys.path.insert(0, str(script.parent))
        sys.argv = ['blender', '--', *script_args]
        exec(compile(tree, str(script), 'exec'), namespace)
    finally:
        sys.argv, sys.path[:] = old_argv, old_path
        write_json(script.parent / (script.stem + '-cpu-execution.json'),
                   {'device': 'CPU', 'renderer': 'CYCLES', 'denoiser': 'OPENIMAGEDENOISE',
                    'renderCalls': render_count, 'hardwareEdits': adapter.edits,
                    'sourceSha256': sha(script), 'visualParityVerified': False})


def compare_images(reference: Path, candidate: Path, report: Path) -> dict[str, Any]:
    import numpy as np
    from PIL import Image
    left = np.asarray(Image.open(reference).convert('RGB'), dtype=np.float64) / 255
    right = np.asarray(Image.open(candidate).convert('RGB'), dtype=np.float64) / 255
    if left.shape != right.shape:
        raise ValueError('Parity comparison requires identical dimensions; images are not rescaled')
    difference = left - right
    mse = float(np.mean(difference**2))
    result = {'referenceSha256': sha(reference), 'candidateSha256': sha(candidate),
              'shape': list(left.shape), 'mae': float(np.mean(abs(difference))),
              'rmse': math.sqrt(mse), 'psnrDB': None if mse == 0 else -10 * math.log10(mse),
              'identical': mse == 0, 'metricSpace': 'display encoded RGB, no registration or resizing',
              'visualAcceptance': 'not implied by these metrics'}
    write_json(report, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare', help='Copy into a fresh CPU workspace outside the checkout')
    prepare.add_argument('--source', type=Path, default=ROOT)
    prepare.add_argument('--workspace', type=Path, required=True)
    verify = commands.add_parser('verify-original')
    verify.add_argument('--workspace', type=Path, required=True)
    gas = commands.add_parser('gas', help='Existing fire/air simulation and optics, on CPU')
    gas.add_argument('material', choices=['fire', 'air'])
    gas.add_argument('--workspace', type=Path, required=True)
    gas.add_argument('--profile', choices=['production', 'smoke'], default='production')
    gas.add_argument('--threads', type=int, default=max(1, min(8, os.cpu_count() or 1)))
    gas.add_argument('--frames', type=int)
    gas.add_argument('--substeps', type=int, default=3)
    gas.add_argument('--save-state', action='store_true')
    render = commands.add_parser('blender', help='Run an existing scene script through CPU Cycles')
    render.add_argument('--workspace', type=Path, required=True)
    render.add_argument('--executable', default='blender')
    render.add_argument('--script', type=Path, required=True)
    render.add_argument('--threads', type=int, default=2)
    render.add_argument('script_args', nargs=argparse.REMAINDER)
    worker = commands.add_parser('_blender-worker')
    worker.add_argument('--script', type=Path, required=True)
    worker.add_argument('--threads', type=int, default=2)
    worker.add_argument('script_args', nargs=argparse.REMAINDER)
    comparison = commands.add_parser('compare')
    comparison.add_argument('reference', type=Path)
    comparison.add_argument('candidate', type=Path)
    comparison.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        result = stage(args.source, args.workspace)
        print(json.dumps({'workspace': result['workspace'], 'copiedFiles': len(result['sourceHashes'])}))
    elif args.command == 'verify-original':
        print(json.dumps(verify_original(args.workspace.resolve())))
    elif args.command == 'gas':
        workspace = args.workspace.resolve()
        if not (workspace / 'cpu-workspace.json').is_file():
            raise RuntimeError('Run prepare first; direct execution in the source checkout is refused')
        try:
            print(json.dumps(run_gas(workspace, args.material, args.profile, args.threads,
                                      args.frames, args.substeps, args.save_state), indent=2))
        finally:
            verify_original(workspace)
    elif args.command == 'blender':
        workspace = args.workspace.resolve()
        if not (workspace / 'cpu-workspace.json').is_file():
            raise RuntimeError('Run prepare first')
        script = (workspace / args.script).resolve()
        if workspace not in script.parents or not script.is_file():
            raise ValueError('Script must be an existing file inside the CPU workspace')
        extra = args.script_args[1:] if args.script_args[:1] == ['--'] else args.script_args
        boot = workspace / 'cpu/blender_entry.py'
        try:
            run_process([executable(args.executable), '--factory-startup', '--background', '--threads', str(args.threads),
                         '--python-exit-code', '1', '--python', str(boot), '--', '--script', str(script),
                         '--threads', str(args.threads), '--', *extra], workspace, args.threads,
                        workspace / 'cpu-logs' / f'{script.stem}.log')
        finally:
            verify_original(workspace)
    elif args.command == '_blender-worker':
        extra = args.script_args[1:] if args.script_args[:1] == ['--'] else args.script_args
        blender_worker(args.script.resolve(), extra, args.threads)
    elif args.command == 'compare':
        print(json.dumps(compare_images(args.reference, args.candidate, args.report), indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, FileNotFoundError, FileExistsError) as error:
        print(f'CPU flow: {error}', file=sys.stderr)
        raise SystemExit(1)
