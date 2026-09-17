"""Measure the velocity effect of contact stopping tolerance on the scene."""
import os,time,json
os.environ.update(CUDA_VISIBLE_DEVICES='0',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
from pathlib import Path
import numpy as np
from scipy.sparse import diags
from scipy.sparse.linalg import splu
from lava_mpm_scene32 import initial
from lava_mpm_reservoir import HotBed
import lava_mpm_cuda_contact27 as backend
import lava_mpm_friction as friction

class Captured(BaseException): pass
cache={};old=backend.try_response;original=friction._sweeps
def remember(A,b,J):
    result=old(A,b,J);cache.update(A=A,b=b,J=J,gpu=result);return result
def check(H,mu,impulse,gradient,steps):
    np.savez_compressed('lava-focus/mpm/rebuild-32/contact-system.npz',H=H,mu=mu,q=gradient)
    start=time.perf_counter();p=np.zeros(len(H));g=gradient.copy();record={}
    for k in range(0,20000,5):
        err=original(H,mu,p,g,5)
        for tol in (1e-7,2e-8,1e-9):
            if err<tol and str(tol) not in record:
                record[str(tol)]=dict(impulse=p.copy(),iterations=k+5,residual=float(err),seconds=time.perf_counter()-start)
        if err<1e-9:break
    reference=p.copy();gpu=cache['gpu'];J=cache['J'];A=cache['A']
    if gpu is not None:solve=gpu.solve
    else:
        sc=1/np.sqrt(A.diagonal());D=diags(sc);fac=splu((D@A@D).tocsc())
        def solve(b):
            x=sc*fac.solve(sc*b)
            for _ in range(2):x+=sc*fac.solve(sc*(b-A@x))
            return x
    ref_velocity=solve(cache['b']-J.T@reference)
    for tol,r in record.items():
        candidate=solve(cache['b']-J.T@r.pop('impulse'))
        r['maximumVelocityDifferenceMPerS']=float(np.max(np.linalg.norm((candidate-ref_velocity).reshape(-1,3),axis=1)))
    report=dict(comparison=record,referenceResidual=float(err),referenceIterations=k+5)
    report['pass']=err<2e-8 and record.get('1e-07',{}).get('maximumVelocityDifferenceMPerS',1)<1e-6
    Path('lava-focus/mpm/rebuild-32/contact-tolerance-proof.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True);raise Captured()
backend.try_response=remember;friction._sweeps=check
s,setup,_=initial();s._solve_deadline=time.monotonic()+180
try:s.step(.0125,bed=HotBed(1450.),boundary=setup['config'])
except Captured:pass
