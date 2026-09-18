"""Clocks, immutable run identities, atomic artifacts, and fail-closed jobs."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import time

SCHEMA = 'cybr-elements/run/1'


@dataclass(frozen=True)
class SceneClock:
    """Frame f samples time f*dt; warmup is simulated before frame zero.

    A movie contains `frames` samples and lasts frames/fps. Its last sampled
    instant is one output interval before that duration. time_scale changes
    physical time, never the encoder's frame rate.
    """
    fps: float = 30.0
    seconds: float = 8.0
    time_scale: float = 1.0
    warmup: float = 0.0

    def __post_init__(self) -> None:
        for name in ('fps', 'seconds', 'time_scale'):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be finite and positive')
        if not math.isfinite(self.warmup) or self.warmup < 0:
            raise ValueError('warmup must be finite and nonnegative')
        if abs(self.seconds * self.fps - round(self.seconds * self.fps)) > 1e-7:
            raise ValueError('seconds*fps must be an integer number of frames')

    @property
    def frames(self) -> int:
        return round(self.seconds * self.fps)

    @property
    def frame_dt(self) -> float:
        return self.time_scale / self.fps

    @property
    def encoder_rate(self) -> str:
        rate = Fraction(str(self.fps)).limit_denominator(100000)
        return f'{rate.numerator}/{rate.denominator}'

    def time(self, frame: int) -> float:
        if not 0 <= frame < self.frames:
            raise ValueError(f'frame {frame} outside [0, {self.frames})')
        return self.warmup + frame * self.frame_dt

    def manifest(self) -> dict[str, Any]:
        return {**asdict(self), 'frames': self.frames,
                'frameDt': self.frame_dt, 'sampleConvention': 'frame-start'}


def select_frames(total: int, mode: str = 'full',
                  explicit: Sequence[int] | None = None, stride: int = 6) -> list[int]:
    if total < 1 or stride < 1:
        raise ValueError('positive frame count and stride required')
    if explicit is not None:
        result = list(explicit)
    elif mode == 'full':
        result = list(range(total))
    elif mode == 'preview':
        result = sorted(set(range(0, total, stride)) | {total - 1})
    else:
        fractions = {
            'pilot': (0., .10, .23, .40, .55, .68, .80, .92, 1.),
            'floor-check': (0., .50, .80, 1.),
            'impact-check': (.55, .65, .75, .85, .95, 1.),
        }
        if mode not in fractions:
            raise ValueError(f'unknown frame-selection mode: {mode}')
        result = sorted({round(x * (total - 1)) for x in fractions[mode]})
    if not result or any(type(f) is not int or not 0 <= f < total for f in result):
        raise ValueError(f'frame selection {result} outside [0, {total})')
    if len(set(result)) != len(result):
        raise ValueError('duplicate frame selection')
    return result


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'),
                         allow_nan=False, default=str).encode('utf8')
    return hashlib.sha256(encoded).hexdigest()


def atomic_bytes(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def atomic_json(path: Path, value: Any) -> None:
    atomic_bytes(path, (json.dumps(value, sort_keys=True, indent=2,
                                  allow_nan=False, default=str) + '\n').encode('utf8'))


def read_json(path: Path) -> Any:
    with Path(path).open(encoding='utf8') as stream:
        return json.load(stream)


def atomic_npz(path: Path, **arrays: Any) -> None:
    import io
    import numpy as np
    stream = io.BytesIO()
    np.savez_compressed(stream, **arrays)
    atomic_bytes(path, stream.getvalue())


class RunIdentity:
    """A run may be resumed only with identical settings and input bytes.

    Receipts bind *every* output to this identity and its content hash. They are
    written after outputs have been atomically installed, never in advance.
    """
    def __init__(self, folder: Path, settings: Mapping[str, Any],
                 inputs: Mapping[str, Path], *, resume: bool = False):
        self.folder = Path(folder).resolve()
        self.folder.mkdir(parents=True, exist_ok=True)
        payload = {'schema': SCHEMA, 'settings': dict(settings),
                   'inputs': {str(k): digest(Path(v)) for k, v in sorted(inputs.items())}}
        self.identity = canonical_hash(payload)
        self.document = {**payload, 'identity': self.identity}
        path = self.folder / 'run.json'
        if path.exists():
            existing = read_json(path)
            if existing.get('identity') != self.identity:
                raise RuntimeError('Run identity mismatch; select a fresh output directory')
            if not resume:
                raise FileExistsError('Run already exists; use --resume with unchanged inputs')
        else:
            if resume:
                raise FileNotFoundError('Cannot resume a run without run.json')
            atomic_json(path, self.document)

    @classmethod
    def open(cls, folder: Path) -> 'RunIdentity':
        """Load the immutable identity for a downstream stage, validating its hash."""
        self = cls.__new__(cls)
        self.folder = Path(folder).resolve()
        self.document = read_json(self.folder / 'run.json')
        self.identity = self.document['identity']
        payload = {key: value for key, value in self.document.items() if key != 'identity'}
        if self.document.get('schema') != SCHEMA or canonical_hash(payload) != self.identity:
            raise RuntimeError('Invalid or modified run identity')
        return self

    def receipt(self, name: str, outputs: Iterable[Path], **metadata: Any) -> dict[str, Any]:
        entries = []
        for output in outputs:
            path = Path(output).resolve()
            path.relative_to(self.folder)
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f'Missing/empty output: {path}')
            entries.append({'path': str(path.relative_to(self.folder)),
                            'sha256': digest(path), 'bytes': path.stat().st_size})
        if not entries:
            raise ValueError('A success receipt must identify at least one artifact')
        result = {'identity': self.identity, 'outputs': entries, **metadata}
        atomic_json(self.folder / 'receipts' / f'{name}.json', result)
        return result

    def verified(self, name: str) -> bool:
        try:
            receipt = read_json(self.folder / 'receipts' / f'{name}.json')
            if receipt['identity'] != self.identity or not receipt['outputs']:
                return False
            for entry in receipt['outputs']:
                path = (self.folder / entry['path']).resolve()
                path.relative_to(self.folder)
                if path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
                    return False
            return True
        except (OSError, ValueError, KeyError, TypeError):
            return False


def stage_status(folder: Path, stage: str, state: str, **details: Any) -> None:
    if state not in {'running', 'complete', 'failed'}:
        raise ValueError('invalid stage state')
    atomic_json(Path(folder) / f'status-{stage}.json',
                {'stage': stage, 'state': state, 'updated': time.time(), **details})


def wait_for(path: Path, *, timeout: float = 600., status: Path | None = None,
             interval: float = .2, predicate: Callable[[Path], bool] | None = None) -> Path:
    """Bounded wait, with immediate propagation of a terminal producer failure."""
    deadline = time.monotonic() + timeout
    while True:
        terminal = None
        if status is not None and Path(status).exists():
            terminal = read_json(status)
            if terminal.get('state') == 'failed':
                raise RuntimeError(f'Producer failed: {terminal.get("error", terminal)}')
        if Path(path).exists() and (predicate is None or predicate(Path(path))):
            return Path(path)
        if terminal and terminal.get('state') == 'complete':
            raise FileNotFoundError(f'Producer completed without required artifact: {path}')
        if time.monotonic() >= deadline:
            raise TimeoutError(f'Timed out waiting for {path}')
        time.sleep(interval)


def blender_executable(requested: str | None = None) -> str:
    candidates = [requested, os.environ.get('BLENDER'), shutil.which('blender')]
    if os.name == 'nt':
        candidates += ['C:/Program Files/Blender Foundation/Blender 4.5/blender.exe']
    for candidate in candidates:
        if candidate and (Path(candidate).is_file() or shutil.which(candidate)):
            return str(candidate)
    raise FileNotFoundError('Blender not found; supply --blender or set BLENDER')


def checked_exit_codes(processes: Iterable[tuple[str, Any]]) -> dict[str, int]:
    """Unconditional final waits are essential, including zero-iteration polls."""
    codes = {name: int(process.wait()) for name, process in processes}
    failures = {name: code for name, code in codes.items() if code != 0}
    if failures:
        raise RuntimeError(f'Child process failure: {failures}')
    return codes


def supervise(commands: Mapping[str, Sequence[str]], folder: Path, *,
              expected: Sequence[Path], timeout: float = 86400.,
              disk_reserve: int = 512 * 1024**2, env: Mapping[str, str] | None = None,
              poll_interval: float = .25) -> dict[str, int]:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    processes: list[tuple[str, subprocess.Popen]] = []
    logs = []
    start = time.monotonic()
    stage_status(folder, 'pipeline', 'running')
    try:
        if not commands or not expected:
            raise ValueError('commands and expected artifacts must be nonempty')
        for name, command in commands.items():
            log = (folder / f'{name}.log').open('w', encoding='utf8')
            logs.append(log)
            process = subprocess.Popen(list(command), stdout=log, stderr=subprocess.STDOUT,
                                       env=dict(env) if env is not None else None)
            processes.append((name, process))
        atomic_json(folder / 'processes.json', {n: p.pid for n, p in processes})
        while any(process.poll() is None for _, process in processes):
            failures = {n: p.returncode for n, p in processes if p.poll() not in (None, 0)}
            if failures:
                raise RuntimeError(f'Child process failure: {failures}')
            if time.monotonic() - start > timeout:
                raise TimeoutError('Pipeline deadline exceeded')
            if shutil.disk_usage(folder).free < disk_reserve:
                raise RuntimeError('Stopped before disk reserve was exhausted')
            time.sleep(poll_interval)
        codes = checked_exit_codes(processes)
        for path in expected:
            if not Path(path).is_file() or Path(path).stat().st_size == 0:
                raise RuntimeError(f'Pipeline exited without required output: {path}')
        stage_status(folder, 'pipeline', 'complete', exitCodes=codes,
                     outputs={str(p): digest(p) for p in expected})
        return codes
    except BaseException as error:
        stage_status(folder, 'pipeline', 'failed', error=str(error))
        raise
    finally:
        for _, process in processes:
            if process.poll() is None:
                process.terminate()
        for _, process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for log in logs:
            log.close()


def prune_after_receipt(path: Path, run: RunIdentity, receipt: str, retention: str) -> None:
    """Opt-in consumption only after a durable, validated downstream milestone."""
    if retention not in {'all', 'rolling'}:
        raise ValueError('retention must be all or rolling')
    if retention == 'rolling':
        Path(path).resolve().relative_to(run.folder)
        if not run.verified(receipt):
            raise RuntimeError('Cannot prune before validated downstream output')
        Path(path).unlink(missing_ok=True)
