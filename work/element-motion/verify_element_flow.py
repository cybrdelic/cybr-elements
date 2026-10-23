"""Differential proof against the pinned pre-extraction films, without a bake.

Loads the original entrypoint functions from Git, not a second solver copy.
Initialization uses their actual coordinate/Fourier contracts. Diagnostic
source fields are explicitly resampled from the retained source.npz; neither
that reduced grid nor this short integration certifies the full film.
"""
import argparse
import ast
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace

import numpy as np
from PIL import Image, __version__ as pillow_version
import torch
import torch.nn.functional as F

from element_flow import CollocatedFlow

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
BASE = '79ae673eee773cda972aaf4a56d1f0f0e1cd79a0'


def baseline(element):
    return subprocess.check_output([
        'git', '-c', f'safe.directory={REPO.as_posix()}', 'show',
        f'{BASE}:work/element-motion/sigil_02_{element}_v2.py',
    ], cwd=REPO).decode('utf-8')


class SourceFields(dict):
    def close(self):
        pass


def fields(size):
    """Only verification grids are resampled; production inputs stay untouched."""
    with np.load(ROOT/'sigil-02-v2/source.npz') as source:
        result = SourceFields()
        for name in ('support', 'arrival', 'dirx', 'dirz', 'sdf'):
            value = torch.from_numpy(source[name])[None, None]
            # Nearest retains infinity/sentinel arrival values without mixing.
            result[name] = F.interpolate(value, size=(size[2], size[0]), mode='nearest')[0,0].numpy()
        return result


def namespace(source, *, size, device, fps=24, control='none'):
    ns = dict(torch=torch, F=F, np=np, math=math, Image=Image,
              CollocatedFlow=CollocatedFlow, fixture_fields=fields(size),
              device=device, ROOT=ROOT,
              a=SimpleNamespace(size=size, fps=fps, substeps=3, padded_domain=False,
                                gesture_version='19', control=control,
                                control_strength=1., wind=.15))
    init = source[source.index('X,Y,Z=a.size'):source.index('rows=[];')]
    init = init.replace("source_fields=np.load(ROOT/'sigil-02-v2/source.npz')", 'source_fields=fixture_fields')
    exec(compile(init, '<original-grid-initialization>', 'exec'), ns)
    functions = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)]
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<film-functions>', 'exec'), ns)
    if 'flow' not in ns:
        ns['flow'] = CollocatedFlow(**{k:ns[k] for k in ('grid','step_scale','dt','h','k','k2','sponge','shape')})
    return ns


def pixels(ns):
    sink = io.BytesIO()
    ns.update(encoder=SimpleNamespace(stdin=sink), TOTAL=294)
    # Frame one avoids the production preview-file branch; the exact original
    # integration, 1920x1080 reconstruction, exposure and transfer are executed.
    ns['render'](1)
    raw = sink.getvalue()
    assert len(raw) == 1920*1080*3
    return np.frombuffer(raw, dtype=np.uint8).reshape(1080,1920,3)


def verify(device):
    results = []
    originals = {}
    for element in ('fire','air'):
        old = baseline(element)
        originals[element] = hashlib.sha256(old.encode()).hexdigest()
        new = (ROOT/f'sigil_02_{element}_v2.py').read_text(encoding='utf-8')
        # Renderer identity is separately checked from a numerical image match.
        def function_text(text, name):
            node = next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name)
            return ast.get_source_segment(text,node)
        assert function_text(old,'render') == function_text(new,'render')
        assert function_text(old,'radiance') == function_text(new,'radiance')
        for fps in (24,30):
            for control in ('none','directed'):
                kwargs = dict(size=(23,10,17),device=device,fps=fps,control=control)
                reference = namespace(old, **kwargs)
                current = namespace(new, **kwargs)
                torch.manual_seed(418)
                seed = torch.rand_like(reference['state'])
                seed[:,:3] = (seed[:,:3]-.5)*14  # Multi-cell departure and sponge edges.
                reference['state'] = seed.clone()
                current['state'] = seed.clone()
                for t in (.4,1.9,7.2):  # Ignition, writing, valve closure; actual policies.
                    before = reference['step'](t)
                    after = current['step'](t)
                    error = float((reference['state']-current['state']).abs().max())
                    assert error == 0, (element,fps,control,t,error)
                    assert before == after
                    assert torch.isfinite(current['state']).all()
                    assert float(current['state'][:,3:].min()) >= 0
                results.append(dict(element=element, simulationFps=fps,control=control,
                                    ticks=3,maxAbsoluteStateError=error,divergenceRms=after))
                if fps==24 and control=='none':
                    before_image, after_image = pixels(reference), pixels(current)
                    assert np.array_equal(before_image, after_image)
                    results[-1]['renderPixelMaxError'] = 0
                    results[-1]['renderSize'] = [1920,1080]

    # Independent operator invariants, including fast departure sampling.
    ns = namespace(old,size=(23,10,17),device=device)
    flow = ns['flow']
    state = torch.zeros_like(ns['state'])
    state[:,3:] = .4
    state[:,0] = 25
    moved = flow.transport(state)
    assert float((moved[:,3:]-.4).abs().max()) < 1e-6
    torch.manual_seed(523)
    state[:,:3] = torch.rand_like(state[:,:3])*2-1
    pre = float(flow.divergence(state[:,:3]).square().mean().sqrt())
    post = flow.project(state)
    assert post < pre*1e-5, (pre,post)
    return dict(referenceCommit=BASE,referenceSourceSha256=originals,device=device,
                cases=results,fullStepComparisons=24,
                constantScalarTransport=True,projectionBefore=pre,projectionAfter=post,
                fullFilmCompared=False,physicalValidation=False)


def diagnostic(device, destination, element='fire'):
    """One real new simulation frame, not a still-derived animation or film."""
    source = (ROOT/f'sigil_02_{element}_v2.py').read_text(encoding='utf-8')
    size = (160,24,90)
    ns = namespace(source,size=size,device=device)
    ns['a'].wind = 0  # Original default film policy.
    frames, substeps, fps = 55, 3, 24
    started = time.monotonic()
    for frame in range(frames):
        for sub in range(substeps):
            div = ns['step']((frame+sub/substeps)/fps)
    image = pixels(ns)
    assert image.max()>0 and torch.isfinite(ns['state']).all()
    destination.mkdir(parents=True,exist_ok=True)
    path = destination/f'{element}-shared-flow-diagnostic.png'
    Image.fromarray(image).save(path)
    state_hash = hashlib.sha256(ns['state'].cpu().numpy().tobytes()).hexdigest()
    receipt = dict(kind='reduced-grid diagnostic, not full-film parity',element=element,
                   size=[1920,1080],solverGrid=list(size),steps=frames*substeps,
                   simulationFps=fps,substeps=substeps,simulationSeconds=frames/fps,
                   elapsedSeconds=time.monotonic()-started,divergenceRms=div,
                   image=path.name,imageSha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                   stateSha256=state_hash,sourceFieldsSha256=hashlib.sha256((ROOT/'sigil-02-v2/source.npz').read_bytes()).hexdigest(),
                   sourceResampling='nearest, full world extent retained',
                   diagnosticWind=0,fullFilmCompared=False)
    (destination/f'{element}-shared-flow-diagnostic.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--diagnostic-dir',type=Path)
    args=parser.parse_args()
    torch.set_num_threads(2)
    torch.set_grad_enabled(False)
    if args.device=='cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA explicitly requested but unavailable')
    result=verify(args.device)
    result.update(torchVersion=torch.__version__,numpyVersion=np.__version__,pillowVersion=pillow_version,
                  gpu=torch.cuda.get_device_name(0) if args.device=='cuda' else None)
    if args.diagnostic_dir:
        result['diagnostic']=diagnostic(args.device,args.diagnostic_dir)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
