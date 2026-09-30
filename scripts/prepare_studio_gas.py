#!/usr/bin/env python3
"""Export fresh fire/air state as native VDB for perspective Cycles rendering."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from rerender_gas import resample_source, load_solver


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind', choices=('fire', 'air'), required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--grid', type=int, nargs=3, default=(192, 40, 108))
    p.add_argument('--frames', type=int, nargs='+', default=list(range(90, 151, 2)))
    p.add_argument('--threads', type=int, default=4)
    a = p.parse_args()
    if not a.frames or min(a.frames) < 0 or max(a.frames) > 293 or min(a.grid) < 8:
        p.error('Expected native frame IDs in 0..293 and grid dimensions >= 8')
    a.output = a.output.resolve()
    if a.output.exists() and any(a.output.iterdir()):
        p.error('Choose a fresh output directory')
    a.output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    config = SimpleNamespace(kind=a.kind, repo=root,
                             source=root/'work/element-motion/sigil-02-v2/source.npz',
                             output=a.output, grid=a.grid, resolution=(1280, 720),
                             fps=30, frames=max(a.frames)+1, substeps=2,
                             threads=a.threads, save_every=30, native_transport=False)
    metadata = resample_source(config, a.output/'sigil-02-v2/source.npz')
    os.environ['OMP_NUM_THREADS'] = str(a.threads)
    import torch
    torch.set_grad_enabled(False)
    namespace, evidence = load_solver(config)
    from density_vdb import vdb, write_density
    # Use the numeric solver bounds rather than reopening the source handle.
    origin = namespace['lo'].copy().astype(np.float64)
    pitch = namespace['extent'].astype(np.float64)/(np.array(a.grid)-1)
    chosen = set(a.frames)
    rows = []
    for f in range(max(a.frames)+1):
        for sub in range(config.substeps):
            div = namespace['step']((f+sub/config.substeps)/30)
        state = namespace['state'][0]
        if not bool(torch.isfinite(state).all()):
            raise FloatingPointError('Nonfinite retained gas state')
        if f not in chosen:
            if f % 30 == 0:
                print(a.kind, 'solve', f, flush=True)
            continue
        soot = state[6].cpu().numpy().transpose(2, 1, 0).astype(np.float32)
        reaction = state[7].cpu().numpy().transpose(2, 1, 0).astype(np.float32)
        temp = state[5].cpu().numpy().transpose(2, 1, 0).astype(np.float32)
        density = soot*2.0 + reaction*.008 if a.kind == 'fire' else soot*3.2
        target = a.output/f'{f:04d}.vdb'
        receipt = write_density(target, density, origin-pitch*.5, pitch)
        grid = vdb.read(str(target), 'density')
        grids = [grid]
        if a.kind == 'fire':
            for name, value in [('temperature', np.maximum(800+temp*1200, 800)), ('reaction', reaction)]:
                g = vdb.FloatGrid(); g.name = name; g.copyFromArray(np.ascontiguousarray(value), tolerance=0)
                g.transform = grid.transform
                grids.append(g)
            vdb.write(str(target), grids=grids)
        rows.append({'frame': f, 'seconds': (f+1)/30, 'divergence_rms': div,
                     'density_sum': float(density.sum()), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                     'mapping': receipt})
        print(a.kind, 'VDB', f, flush=True)
    report = {'element': a.kind, 'grid': a.grid, 'frames': a.frames,
              'fps': 30, 'substeps': config.substeps, 'freshSolvedState': True,
              'oldFilmPixelsUsed': False, 'source': metadata, 'solver': evidence, 'states': rows}
    (a.output/'gas-report.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
