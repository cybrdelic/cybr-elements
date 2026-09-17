"""One accepted-cache step with bounded sparse-factor memory diagnostics."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import json,time,traceback
import numpy as np,psutil
import lava_mpm_friction as friction
import lava_mpm_sparse_pressure as pressure
from lava_mpm import ROOT,MPM
from lava_mpm_continuous import HotBed
original=friction.splu
def trace(A,**kwargs):
    A.eliminate_zeros()
    print(json.dumps(dict(event='factor',shape=A.shape,nnz=A.nnz,privateMiB=psutil.Process().memory_info().private/2**20,symmetricError=float(np.max(abs((A-A.T).data),initial=0)))),flush=True)
    t=time.monotonic();out=original(A,**kwargs)
    print(json.dumps(dict(event='factored',seconds=time.monotonic()-t,nonzeros=out.L.nnz+out.U.nnz,privateMiB=psutil.Process().memory_info().private/2**20)),flush=True)
    return out
friction.splu=pressure.splu=trace
s=MPM.load(ROOT/'rebuild-25'/'thermal-screen');s._solve_deadline=time.monotonic()+45
try:
    row=s.step(.25,bed=HotBed(1450.));print(json.dumps(row),flush=True)
except Exception:traceback.print_exc()
