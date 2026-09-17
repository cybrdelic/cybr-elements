"""Compare bounded GPU contact response against CPU on the actual crust system."""
import os,time,json
os.environ.update(CUDA_VISIBLE_DEVICES='0',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
from pathlib import Path
import numpy as np
from scipy.sparse import diags
from scipy.sparse.linalg import splu
from lava_mpm_scene32 import initial
from lava_mpm_reservoir import HotBed
import lava_mpm_cuda_contact27 as backend

class Captured(BaseException): pass
def compare(Ar,br,J):
    start=time.perf_counter()
    sc=1/np.sqrt(Ar.diagonal());D=diags(sc)
    fac=splu((D@Ar@D).tocsc(),permc_spec='MMD_AT_PLUS_A',diag_pivot_thresh=0.,options={'SymmetricMode':True})
    def solve(b):
        q=sc[:,None] if b.ndim==2 else sc
        x=q*fac.solve(q*b)
        for _ in range(2): x+=q*fac.solve(q*(b-Ar@x))
        return x
    selected=np.unique(np.linspace(0,J.shape[0]-1,20).astype(int))
    B=np.column_stack([br,J[selected].T.toarray()]);cpu=solve(B)
    cpu_seconds=time.perf_counter()-start
    gpu=backend.ContactResponse(Ar,br,J)
    h_ref=J@cpu[:,1:]
    report=dict(dofs=Ar.shape[0],directions=J.shape[0],cpuSeconds=cpu_seconds,
        freeRelativeError=float(np.linalg.norm(gpu.free-cpu[:,0])/max(np.linalg.norm(cpu[:,0]),1e-30)),
        responseRelativeError=float(np.linalg.norm(gpu.H[:,selected]-h_ref)/max(np.linalg.norm(h_ref),1e-30)),
        freeStationarity=float(np.linalg.norm(Ar@gpu.free-br)/max(np.linalg.norm(br),1e-30)),
        gpu=backend.metrics())
    report['pass']=max(report['freeRelativeError'],report['responseRelativeError'],report['freeStationarity'])<1e-5
    Path('lava-focus/mpm/rebuild-32/contact-response-proof.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)
    raise Captured()

backend.try_response=compare
s,setup,_=initial()
s._solve_deadline=time.monotonic()+180
try:s.step(.001,bed=HotBed(1450.),boundary=setup['config'])
except Captured:pass
