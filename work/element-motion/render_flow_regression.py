"""Full style-02 baseline/shared film with per-frame state and pixel receipts.

Outputs must use a new directory. Runs one solver at a time, preserving the
original 294-frame/1080p film, source, optics and frame-135 review gate. This
proves extraction parity at the explicitly selected simulation clock; it does
not recover the missing historical CLI or validate combustion physics.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from PIL import Image
import numpy as np
import torch

from verify_element_flow import ROOT, BASE, baseline, namespace, pixels


def state_digest(state):
    """Hash C-order state bytes with bounded host memory (under 13 MiB/slab).

    Iteration follows batch, channel, z, y, x, exactly matching the original
    contiguous whole-state readback. No quantization or numerical conversion.
    """
    digest=hashlib.sha256()
    for batch in state:
        for channel in batch:
            for start in range(0,channel.shape[0],64):
                slab=channel[start:start+64].contiguous().cpu()
                digest.update(memoryview(slab.numpy()))
                del slab
    return digest.hexdigest()


def validate_source(source_fields):
    """Full-film runs never silently resize an incomplete/reduced-grid input."""
    with np.load(source_fields) as source:
        for name in ('support','sdf','arrival','dirx','dirz'):
            value=source[name]
            if value.shape!=(504,896) or value.dtype!=np.float32 or not np.isfinite(value).all():
                raise ValueError(f'Full-grid float32 finite source field required: {name}')
        for name,expected in (('lo',[-7.,-.6,-1.05]),('extent',[14.,1.2,7.875])):
            if not np.array_equal(source[name].astype(np.float32),np.asarray(expected,np.float32)):
                raise ValueError(f'Source world-coordinate contract mismatch: {name}')


def run(args):
    torch.set_num_threads(2)
    torch.set_grad_enabled(False)
    if not torch.cuda.is_available():
        raise RuntimeError('Full production regression requires CUDA')
    if args.output.exists():
        raise FileExistsError('Use a new output directory; existing evidence is preserved')
    args.output.mkdir(parents=True)
    source = baseline(args.element) if args.version=='baseline' else (ROOT/f'sigil_02_{args.element}_v2.py').read_text(encoding='utf-8')
    source_fields=args.source_fields or ROOT/'sigil-02-v2/source.npz'
    validate_source(source_fields)
    ns = namespace(source,size=(896,56,504),device='cuda',fps=args.simulation_fps,source_path=source_fields)
    ns['a'].wind = 0
    video = args.output/f'{args.element}-{args.version}.mp4'
    reference = None
    if args.reference:
        reference = [json.loads(line) for line in args.reference.read_text().splitlines()]
        if len(reference)!=294:raise ValueError('Reference must contain all 294 frames')
    encoder = subprocess.Popen([
        'ffmpeg','-hide_banner','-loglevel','error','-n','-f','rawvideo',
        '-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','-','-an',
        '-c:v','libx264','-threads','2','-preset','fast','-crf','17',
        '-pix_fmt','yuv420p','-movflags','+faststart',str(video),
    ],stdin=subprocess.PIPE)
    started = time.monotonic()
    metadata = dict(element=args.element,version=args.version,referenceCommit=BASE,
                    runnerSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    harnessSha256=hashlib.sha256((ROOT/'verify_element_flow.py').read_bytes()).hexdigest(),
                    sourceSha256=hashlib.sha256(source.encode()).hexdigest(),
                    sharedCoreSha256=hashlib.sha256((ROOT/'element_flow.py').read_bytes()).hexdigest() if args.version=='shared' else None,
                    sourceFieldsSha256=hashlib.sha256(source_fields.read_bytes()).hexdigest(),
                    sourceKind='custom example' if args.source_fields else 'approved style-02',
                    stateHashReadback='exact C-order float32 bytes, streamed in 64-plane slabs',
                    solverGrid=[896,56,504],size=[1920,1080],frames=294,encodedFps=30,
                    simulationFps=args.simulation_fps,substeps=3,simulationSeconds=294/args.simulation_fps,
                    historicalInvocationRecovered=False,wind=0,control='none',
                    torchVersion=torch.__version__,gpu=torch.cuda.get_device_name(0),
                    diagnostic=False,physicalValidation=False)
    (args.output/'run.json').write_text(json.dumps(metadata,indent=2)+'\n')
    mismatch = []
    completed = False
    try:
        with (args.output/'frames.jsonl').open('w',encoding='utf-8') as receipts:
            for frame in range(294):
                for sub in range(3):
                    div=ns['step']((frame+sub/3)/args.simulation_fps)
                if not torch.isfinite(ns['state']).all():raise RuntimeError(f'Nonfinite state at {frame}')
                if torch.cuda.max_memory_allocated()>6.8*1024**3:raise RuntimeError('Original GPU memory budget exceeded')
                state_sha = state_digest(ns['state'])
                image = pixels(ns)
                pixel_sha = hashlib.sha256(memoryview(image)).hexdigest()
                encoder.stdin.write(image.tobytes())
                row=dict(frame=frame,stateSha256=state_sha,pixelSha256=pixel_sha,
                         divergenceRms=div,elapsedSeconds=round(time.monotonic()-started,3))
                if reference is not None:
                    match = all(reference[frame][key]==row[key] for key in ('frame','stateSha256','pixelSha256'))
                    row['referenceMatch']=match
                    if not match:mismatch.append(frame)
                if frame in (30,60,135,210,293):
                    png=args.output/f'frame-{frame:03}.png'
                    Image.fromarray(image).save(png)
                    row['image']=png.name
                    row['imageSha256']=hashlib.sha256(png.read_bytes()).hexdigest()
                receipts.write(json.dumps(row)+'\n');receipts.flush()
                if frame%15==0 or frame==293:
                    print(json.dumps(dict(row,peakGpuMiB=round(torch.cuda.max_memory_allocated()/1048576,2))),flush=True)
                if frame==135:
                    print(f'Frame 135 visual review gate: create {args.gate_file} after inspecting frame-135.png',flush=True)
                    while not args.gate_file.exists():time.sleep(.5)
        encoder.stdin.close()
        if encoder.wait()!=0:raise RuntimeError('Encoding failed')
        completed = True
    finally:
        if not completed:
            if encoder.stdin and not encoder.stdin.closed:encoder.stdin.close()
            encoder.wait()
    metadata.update(completed=True,elapsedSeconds=time.monotonic()-started,
                    peakGpuMiB=torch.cuda.max_memory_allocated()/1048576,
                    video=video.name,videoSha256=hashlib.sha256(video.read_bytes()).hexdigest(),
                    comparedToBaseline=reference is not None,mismatchingFrames=mismatch,
                    all294StateAndPixelHashesEqual=(not mismatch) if reference is not None else None)
    (args.output/'complete.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata,indent=2),flush=True)
    if mismatch:raise RuntimeError(f'Baseline parity failed for {len(mismatch)} frames')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--element',choices=['fire','air'],required=True)
    p.add_argument('--version',choices=['baseline','shared'],required=True)
    p.add_argument('--simulation-fps',type=int,choices=[24,30],required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--gate-file',type=Path,required=True)
    p.add_argument('--reference',type=Path,help='Baseline frames.jsonl for the shared run')
    p.add_argument('--source-fields',type=Path,help='Optional explicit NPZ for a new source example; original source stays untouched')
    run(p.parse_args())
