"""Capture a real lava pressure system and compare identical objectives.

All artifacts are CPU data; the benchmark is separate from visual acceptance.
"""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import argparse,json,time
from pathlib import Path
import numpy as np
from scipy.sparse import save_npz,load_npz
from lava_mpm import ROOT,SOURCE_HASHES

FOLDER=ROOT/'rebuild-26'/'pressure-proof'


def capture():
    import lava_mpm_sparse_pressure as pressure
    from lava_mpm_scene26 import run
    FOLDER.mkdir(parents=True,exist_ok=True);actual=pressure.contact;captured=False
    def wrapped(A,rhs,S,C,compliance,offset=None,**kwargs):
        nonlocal captured
        if not captured:
            for key,value in dict(A=A,S=S,C=C).items():save_npz(FOLDER/(key+'.npz'),value)
            np.savez_compressed(FOLDER/'vectors.npz',rhs=rhs,compliance=np.broadcast_to(compliance,(C.shape[0],)),offset=np.zeros(C.shape[0]) if offset is None else offset)
            (FOLDER/'input.json').write_text(json.dumps(dict(source='First pressure system from hot-inlet continuous-crust case',shape=A.shape,constraints=C.shape[0],sourceHashes=SOURCE_HASHES),indent=2))
            captured=True
        return actual(A,rhs,S,C,compliance,offset,**kwargs)
    pressure.contact=wrapped
    return run('hot-inlet',.5,120.,.02)


def compare():
    # This experiment was rejected: equivalent output, slower on the
    # captured case. Keep it outside the live solver for reproducibility.
    import importlib.util
    spec=importlib.util.spec_from_file_location('pressure_predictor_experiment',FOLDER/'predictor-experiment.py')
    candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
    contact=candidate.contact
    A,S,C=[load_npz(FOLDER/(key+'.npz')) for key in ('A','S','C')]
    q=np.load(FOLDER/'vectors.npz');results={};states={}
    for mode in ('free','bilateral'):
        start=time.perf_counter();r=contact(A,q['rhs'],S,C,q['compliance'],q['offset'],initialization=mode)
        states[mode]=r
        results[mode]=dict(seconds=time.perf_counter()-start,iterations=r[4],residual=r[1])
    error=float(np.linalg.norm(states['free'][0]-states['bilateral'][0])/max(np.linalg.norm(states['free'][0]),1e-20))
    pressure_error=float(np.linalg.norm(states['free'][2]-states['bilateral'][2])/max(np.linalg.norm(states['free'][2]),1e-20))
    report=dict(status='pass' if error<1e-5 and pressure_error<1e-5 else 'fail',velocityRelativeDifference=error,multiplierRelativeDifference=pressure_error,results=results,sourceHashes=SOURCE_HASHES,
        retainedInSolver=False,scope='Rejected performance experiment, preserved outside the live solver. One captured lava system; same contact objective and tolerances. This is not visual, full-fracture or timestep acceptance.')
    (FOLDER/'comparison.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
    assert report['status']=='pass'


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['capture','compare']);a=p.parse_args()
    if a.mode=='capture':capture()
    else:compare()
