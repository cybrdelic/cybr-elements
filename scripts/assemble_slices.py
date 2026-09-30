#!/usr/bin/env python3
"""Verify freshly rendered shard ZIPs and assemble an unchanged native film.

Usage:
  python assemble_slices.py --kind water --commit FULL_COMMIT \
    --digests water-digests.json downloaded-slice-*.zip
  python assemble_slices.py --kind earth --commit FULL_COMMIT \
    --input-directory downloaded-artifacts --output-directory merged-delivery

Digest JSON is {archiveBasename: SHA256hex}; a GitHub 'sha256:' prefix is also
accepted. Only water (240 frames), earth/ice/lava/lightning (300) are supported.
Production encoding is fixed to native 1280x720, 30 fps, H.264 CRF 17 yuv420p.
No image is resized, synthesized, blended, interpolated or remapped here.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct
import subprocess
import tempfile
import time
import zipfile

from PIL import Image

KINDS = ('water', 'earth', 'ice', 'lava', 'lightning')
MAX_SHARD_BYTES = 1024**3
MAX_MEMBER_BYTES = 64 * 1024**2
MAX_MEMBERS = 10_000
IDENTITIES = ('sourceSha256', 'inputSha256', 'cacheSha256', 'physicsSha256')


@dataclass(frozen=True)
class Contract:
    frames: int
    resolution: tuple[int, int] = (1280, 720)
    fps: int = 30


def production_contract(kind):
    if kind not in KINDS:
        raise ValueError('Unknown shard element')
    return Contract(240 if kind == 'water' else 300)


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checksum(value, label):
    if isinstance(value, str) and value.startswith('sha256:'):
        value = value[7:]
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError(f'Invalid SHA-256: {label}')
    return value


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f'Nonfinite JSON value: {value}')
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs,
                      parse_constant=invalid)


def relative(value, *, directory=False):
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        raise ValueError('Unsafe archive or receipt path')
    if directory and value.endswith('/'):
        value = value[:-1]
    if (not value or value.startswith('/') or '\\' in value or ':' in value
            or any(part in ('', '.', '..') for part in value.split('/'))):
        raise ValueError(f'Unsafe archive or receipt path: {value!r}')
    return PurePosixPath(value)


def digest_map(value, label, *, file_paths=False, nonempty=True):
    if not isinstance(value, dict) or (nonempty and not value):
        raise ValueError(f'Missing hash map: {label}')
    result = {}
    for key, digest in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError(f'Invalid hash label: {label}')
        if file_paths:
            relative(key)
        result[key] = checksum(digest, f'{label}/{key}')
    return result


def extract_checked(archive_path, target):
    """Extract only bounded regular files into a private, fresh directory."""
    target.mkdir()
    with zipfile.ZipFile(archive_path) as bundle:
        entries = bundle.infolist()
        if len(entries) > MAX_MEMBERS or sum(entry.file_size for entry in entries) > MAX_SHARD_BYTES:
            raise ValueError('Shard archive exceeds extraction budget')
        names = set()
        for entry in entries:
            path = relative(entry.orig_filename, directory=entry.is_dir())
            canonical = path.as_posix()
            if canonical in names:
                raise ValueError(f'Duplicate ZIP member: {canonical}')
            names.add(canonical)
            mode = entry.external_attr >> 16
            if (mode & 0o170000) not in (0, 0o100000, 0o040000) or entry.flag_bits & 1:
                raise ValueError(f'Nonregular or encrypted ZIP member: {canonical}')
            if not entry.is_dir() and (mode & 0o170000) == 0o040000:
                raise ValueError('ZIP directory mode disagrees with its filename')
            if not entry.is_dir() and entry.file_size > MAX_MEMBER_BYTES:
                raise ValueError(f'Shard member exceeds extraction budget: {canonical}')
            if entry.is_dir() and entry.file_size:
                raise ValueError('Directory member contains a payload')
        for entry in entries:
            path = relative(entry.orig_filename, directory=entry.is_dir())
            destination = target.joinpath(*path.parts)
            if entry.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            total = 0
            with bundle.open(entry) as source, destination.open('xb') as output:
                while True:
                    chunk = source.read(min(1024**2, entry.file_size - total + 1))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > entry.file_size:
                        raise ValueError(f'ZIP member exceeds declared bytes: {entry.filename}')
                    output.write(chunk)
            if total != entry.file_size:
                raise ValueError(f'Truncated ZIP member: {entry.filename}')
    summaries = list(target.rglob('slice-summary.json'))
    if len(summaries) != 1:
        raise ValueError('Each shard must contain exactly one slice-summary.json')
    if any(not path.is_relative_to(summaries[0].parent) for path in target.rglob('*') if path.is_file()):
        raise ValueError('Shard contains files outside its receipt directory')
    return summaries[0].parent


def copied_directory(source, target):
    """Safely snapshot an artifact already extracted by download-artifact."""
    source = Path(source)
    paths = list(source.rglob('*'))
    if len(paths) > MAX_MEMBERS:
        raise ValueError('Extracted shard exceeds member budget')
    total = 0
    for path in [source, *paths]:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise ValueError('Extracted shard contains symlinks or nonregular files')
        if stat.S_ISREG(info.st_mode):
            if info.st_size > MAX_MEMBER_BYTES:
                raise ValueError('Extracted shard member exceeds byte budget')
            total += info.st_size
    if total > MAX_SHARD_BYTES:
        raise ValueError('Extracted shard exceeds byte budget')
    shutil.copytree(source, target)
    return target


def check_summary(root, kind, commit, contract):
    summary = read_json(root / 'slice-summary.json')
    if not isinstance(summary, dict) or summary.get('version') != 1:
        raise ValueError('Unsupported slice receipt version')
    if summary.get('kind') != kind or summary.get('sourceCommit') != commit:
        raise ValueError('Shard element or sourceCommit mismatch')
    if summary.get('freshPixels') is not True or summary.get('oldFilmPixelsUsed') is not False:
        raise ValueError('Shard does not attest freshly rendered pixels')
    start, end = summary.get('start'), summary.get('end')
    if (type(start) is not int or type(end) is not int
            or not 0 <= start < end <= contract.frames):
        raise ValueError('Invalid delivered frame interval')
    frame_ids = summary.get('frameIDs')
    if (not isinstance(frame_ids, list) or any(type(frame) is not int for frame in frame_ids)
            or frame_ids != list(range(start, end))):
        raise ValueError('frameIDs must exactly match the delivered half-open interval')
    settings = summary.get('settings')
    samples = 16 if kind == 'earth' else 64 if kind == 'lightning' else 24
    if (not isinstance(settings, dict) or settings.get('resolution') != list(contract.resolution)
            or settings.get('fps') != contract.fps or settings.get('samples') != samples
            or type(settings.get('threads')) is not int or not 1 <= settings['threads'] <= 64
            or settings.get('engine') not in ('CYCLES', 'BLENDER_EEVEE_NEXT')
            or settings['engine'] != ('BLENDER_EEVEE_NEXT' if kind == 'lightning' else 'CYCLES')
            or (kind in ('ice', 'lava') and settings.get('volumeFormat') != 'atlas')
            or (kind == 'lightning' and settings.get('volumeFormat') != 'native-vdb')):
        raise ValueError('Shard native settings differ from the production contract')
    identities = {key: digest_map(summary.get(key), key, file_paths=key in ('sourceSha256', 'inputSha256'))
                  for key in IDENTITIES}
    frames = digest_map(summary.get('frameSha256'), 'frameSha256', file_paths=True)
    reports = digest_map(summary.get('reportSha256'), 'reportSha256', file_paths=True)
    extension = '.png' if kind == 'earth' else '.jpg'
    expected = {f'frames/{frame:04d}{extension}' for frame in frame_ids}
    if set(frames) != expected:
        raise ValueError('Frame hash map does not exactly cover delivered frame IDs')
    if any(not path.startswith('reports/') for path in reports):
        raise ValueError('Preserved report files must be inside reports/')
    files = {path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file()}
    if files != set(frames) | set(reports) | {'slice-summary.json'}:
        raise ValueError('Shard contains missing or unreceipted files')
    for label, hashes in (('frame', frames), ('report', reports)):
        for name, expected_hash in hashes.items():
            path = root.joinpath(*relative(name).parts)
            if not path.is_file() or sha256(path) != expected_hash:
                raise ValueError(f'{label.capitalize()} hash mismatch: {name}')
    for name in sorted(frames):
        with Image.open(root / name) as image:
            if image.size != contract.resolution or image.format != ('PNG' if kind == 'earth' else 'JPEG'):
                raise ValueError(f'Frame native resolution or image type mismatch: {name}')
            image.load()
    mapping = summary.get('frameMapping')
    if kind == 'earth':
        if (not isinstance(mapping, dict) or set(mapping) != {str(frame) for frame in frame_ids}
                or any(type(source) is not int or not 0 <= source < 390 for source in mapping.values())):
            raise ValueError('Earth must retain every authored delivered-to-physical frame mapping')
        full_maps = []
        for name in reports:
            if name.endswith('.json'):
                report = read_json(root / name)
                if isinstance(report, dict):
                    full = report.get('outputFrameMap', report.get('fulloutputFrameMap'))
                    if full is not None:
                        full_maps.append(full)
        if (not full_maps or any(not isinstance(full, list) or len(full) != contract.frames for full in full_maps)
                or any(full != full_maps[0] for full in full_maps[1:])
                or any(mapping[str(frame)] != full_maps[0][frame] for frame in frame_ids)):
            raise ValueError('Earth slice mapping differs from its preserved full authored mapping')
    elif mapping not in (None, {}):
        raise ValueError('Unexpected remapping of a native frame sequence')
    return summary, identities, frames, reports


def run(command, log=None):
    process = subprocess.run([str(arg) for arg in command], capture_output=True, text=True)
    if log is not None:
        Path(log).write_text(process.stdout + process.stderr, encoding='utf-8')
    if process.returncode:
        raise RuntimeError(f'{Path(str(command[0])).name} failed ({process.returncode}): {process.stderr[-6000:]}')
    return process.stdout


def faststart_verified(path):
    offsets = {}
    total = Path(path).stat().st_size
    with Path(path).open('rb') as stream:
        offset = 0
        while offset < total:
            stream.seek(offset)
            header = stream.read(8)
            if len(header) != 8:
                raise ValueError('Truncated MP4 atom header')
            size, tag = struct.unpack('>I4s', header)
            minimum = 8
            if size == 1:
                extra = stream.read(8)
                if len(extra) != 8:
                    raise ValueError('Truncated extended MP4 atom')
                size = struct.unpack('>Q', extra)[0]
                minimum = 16
            elif size == 0:
                size = total - offset
            if size < minimum or offset + size > total:
                raise ValueError('Invalid MP4 atom size')
            offsets.setdefault(tag, offset)
            offset += size
    if b'moov' not in offsets or b'mdat' not in offsets or offsets[b'moov'] > offsets[b'mdat']:
        raise ValueError('MP4 is missing a verified faststart index')
    return True


def encode(stage, kind, contract, extension, threads, ffmpeg, ffprobe):
    movie = stage / f'cybr-elements-{kind}-rerender.mp4'
    command = [ffmpeg, '-v', 'error', '-n', '-framerate', contract.fps, '-start_number', 0,
               '-i', stage / 'frames' / f'%04d{extension}', '-frames:v', contract.frames,
               '-c:v', 'libx264', '-preset', 'slow', '-crf', 17, '-pix_fmt', 'yuv420p',
               '-movflags', '+faststart', '-threads', threads, '-fps_mode', 'passthrough', '-an', movie]
    run(command, stage / 'encode.log')
    probe = json.loads(run([ffprobe, '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                           '-show_entries', 'stream=codec_name,pix_fmt,width,height,avg_frame_rate,r_frame_rate,nb_read_frames,nb_frames,duration:format=duration',
                           '-of', 'json', movie]))
    streams = probe.get('streams', [])
    if len(streams) != 1:
        raise ValueError('Assembled film must contain exactly one video stream')
    stream = streams[0]
    if (stream.get('codec_name') != 'h264' or stream.get('pix_fmt') != 'yuv420p'
            or [stream.get('width'), stream.get('height')] != list(contract.resolution)
            or Fraction(stream.get('avg_frame_rate', '0/1')) != contract.fps
            or Fraction(stream.get('r_frame_rate', '0/1')) != contract.fps
            or int(stream.get('nb_read_frames', -1)) != contract.frames
            or int(stream.get('nb_frames', -1)) != contract.frames):
        raise ValueError('Assembled film failed native codec/cadence/count/resolution validation')
    duration = float(probe.get('format', {}).get('duration', -1))
    if not math.isfinite(duration) or abs(duration - contract.frames / contract.fps) > 1 / contract.fps:
        raise ValueError('Assembled film duration differs from its unchanged native cadence')
    decoded = run([ffmpeg, '-v', 'error', '-xerror', '-i', movie, '-map', '0:v:0', '-an', '-sn',
                   '-fps_mode', 'passthrough', '-f', 'framemd5', '-'])
    rows = [line for line in decoded.splitlines() if line and not line.startswith('#')]
    if len(rows) != contract.frames:
        raise ValueError('Full film decoding did not produce every expected frame')
    (stage / 'decode-framemd5.txt').write_text(decoded, encoding='utf-8')
    faststart_verified(movie)
    return movie, probe, {'codec': 'h264', 'crf': 17, 'pixelFormat': 'yuv420p',
                          'fps': contract.fps, 'decodedFrames': len(rows), 'faststartVerified': True,
                          'command': [str(arg) for arg in command]}


def assemble(archives, digests, kind, commit, destination, *, threads=4,
             ffmpeg='ffmpeg', ffprobe='ffprobe', contract=None, input_directory=None):
    """Assemble once; the optional internal contract supports disposable CPU tests."""
    begun = time.monotonic()
    contract = production_contract(kind) if contract is None else contract
    if kind not in KINDS or not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('A supported element and exact 40-character source commit are required')
    if type(threads) is not int or not 1 <= threads <= 64:
        raise ValueError('Encoding threads must be between 1 and 64')
    destination = Path(destination)
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or any(destination.iterdir()))):
        raise ValueError('Choose a fresh empty artifact destination; existing frames or films are preserved')
    archives = [Path(path).resolve() for path in archives]
    if input_directory is not None:
        if archives or digests:
            raise ValueError('Choose extracted directories or ZIP archives, never both')
        input_directory = Path(input_directory).resolve()
        if not input_directory.is_dir() or destination.resolve().is_relative_to(input_directory):
            raise ValueError('Input must be a directory separate from the output artifact')
        if any(path.is_symlink() for path in input_directory.rglob('*')):
            raise ValueError('Artifact input directory contains a symbolic link')
        originals = sorted(path.parent for path in input_directory.rglob('slice-summary.json'))
        if not originals or any(first != second and first.is_relative_to(second)
                                for first in originals for second in originals):
            raise ValueError('Artifact directories must contain disjoint slice receipts')
        sources = [(path.relative_to(input_directory).as_posix() or 'root', path, False) for path in originals]
        digests = {}
    else:
        names = [path.name for path in archives]
        digests = digest_map(digests, 'archive digests')
        if len(names) != len(set(names)) or set(names) != set(digests):
            raise ValueError('Archive basenames and supplied digest mapping must match exactly')
        for archive in archives:
            if not archive.is_file() or sha256(archive) != digests[archive.name]:
                raise ValueError(f'Archive digest mismatch: {archive.name}')
        sources = [(archive.name, archive, True) for archive in archives]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f'.assemble-{kind}-', dir=destination.parent) as temporary:
        stage = Path(temporary) / 'artifact'
        stage.mkdir()
        (stage / 'shards').mkdir()
        (stage / 'frames').mkdir()
        baseline = None
        receipts, frame_hashes, report_hashes, mappings = [], {}, {}, {}
        worker_seconds = []
        for index, (label, original, is_archive) in enumerate(sources):
            shard = stage / 'shards' / f'{index:03d}'
            root = extract_checked(original, shard) if is_archive else copied_directory(original, shard)
            summary, identities, frames, reports = check_summary(root, kind, commit, contract)
            identity = {'settings': summary['settings'], **identities}
            if baseline is None:
                baseline = identity
            elif baseline != identity:
                raise ValueError('Independent shards differ in source/input/physics/cache hashes or native settings')
            if set(frame_hashes) & set(frames):
                raise ValueError('Shard delivered frame IDs overlap')
            for name, digest in frames.items():
                destination_frame = stage / name
                shutil.copy2(root / name, destination_frame)
                if sha256(destination_frame) != digest:
                    raise ValueError('Copying a verified frame changed its bytes')
            frame_hashes.update(frames)
            for name, digest in reports.items():
                copied_name = (root / name).relative_to(stage).as_posix()
                report_hashes[copied_name] = digest
            if kind == 'earth':
                mappings.update(summary['frameMapping'])
            seconds = summary.get('elapsedSeconds', 0)
            if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not math.isfinite(seconds) or seconds < 0:
                raise ValueError('Invalid shard elapsedSeconds')
            worker_seconds.append(seconds)
            transport = ({'archive': label, 'archiveSha256': digests[label]} if is_archive
                         else {'artifactDirectory': label, 'transport': 'download-artifact extracted directory'})
            receipts.append({**transport, 'start': summary['start'], 'end': summary['end'],
                             'receipt': (root / 'slice-summary.json').relative_to(stage).as_posix(),
                             'receiptSha256': sha256(root / 'slice-summary.json')})
            print(f'Verified {label}: delivered frames {summary["start"]}..{summary["end"]-1}', flush=True)
        extension = '.png' if kind == 'earth' else '.jpg'
        expected = {f'frames/{frame:04d}{extension}' for frame in range(contract.frames)}
        if set(frame_hashes) != expected:
            missing = sorted(expected - set(frame_hashes))
            raise ValueError(f'Shards do not cover the full original frame sequence; missing {missing[:10]}')
        # Ordering is the delivered timeline, already authored by the producer.
        # Earth's repeated/reversed physical frames are copied without remapping.
        movie, probe, encoding = encode(stage, kind, contract, extension, threads, ffmpeg, ffprobe)
        summary = dict(complete=True, element=kind, sourceCommit=commit, nativeResolution=list(contract.resolution),
                       fps=contract.fps, frames=contract.frames, freshFrames=True, oldFilmPixelsUsed=False,
                       sourceSha256=baseline['sourceSha256'], inputSha256=baseline['inputSha256'],
                       cacheSha256=baseline['cacheSha256'], physicsSha256=baseline['physicsSha256'],
                       settings=baseline['settings'], movieSha256=sha256(movie),
                       frameSha256=dict(sorted(frame_hashes.items())), reportSha256=dict(sorted(report_hashes.items())),
                       shards=sorted(receipts, key=lambda receipt: receipt['start']), probe=probe['streams'][0],
                       encoding=encoding, assemblySeconds=time.monotonic()-begun,
                       elapsedSeconds=(time.monotonic()-begun)+max(worker_seconds, default=0),
                       workerElapsedSecondsTotal=sum(worker_seconds), fullDecodeVerified=True)
        if kind == 'earth':
            summary['frameMapping'] = {str(frame): mappings[str(frame)] for frame in range(contract.frames)}
            summary['earthEditorialMappingPreserved'] = True
        (stage / 'render-summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        # Original shard frames and reports remain alongside the assembled
        # sequence. Input ZIPs are never rewritten, moved or deleted.
        if destination.exists():
            destination.rmdir()  # Only an empty directory can be removed.
        stage.rename(destination)
    return destination / movie.name, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archives', type=Path, nargs='*')
    parser.add_argument('--kind', choices=KINDS, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--digests', type=Path)
    parser.add_argument('--input-directory', type=Path)
    parser.add_argument('--destination', '--output-directory', dest='destination', type=Path)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--ffprobe', default='ffprobe')
    args = parser.parse_args(argv)
    if args.input_directory:
        if args.archives or args.digests:
            parser.error('--input-directory cannot be combined with archives or --digests')
    elif not args.archives or not args.digests:
        parser.error('Provide --input-directory, or ZIP archives plus --digests')
    destination = args.destination or Path(__file__).resolve().parents[1] / 'work/render-slices/assembled' / args.kind
    try:
        movie, summary = assemble(args.archives, read_json(args.digests) if args.digests else {}, args.kind, args.commit, destination,
                                  threads=args.threads, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe,
                                  input_directory=args.input_directory)
    except (OSError, ValueError, RuntimeError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, f'Shard assembly failed: {error}\n')
    print(json.dumps({'element': args.kind, 'path': str(movie), 'movieSha256': summary['movieSha256'],
                      'frames': summary['frames'], 'decodedFrames': summary['encoding']['decodedFrames'],
                      'nativeResolution': summary['nativeResolution'], 'shards': len(summary['shards'])}), flush=True)


if __name__ == '__main__':
    main()
