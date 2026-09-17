from lava_mpm_suspended34 import initial
from lava_mpm_reservoir import HotBed
import lava_mpm_sparse_pressure as solver
import numpy as np,json
from scipy.sparse import save_npz
class Captured(BaseException):pass
def capture(A,**kwargs):
    a=A.tocsr();d=a.diagonal();norm=np.asarray(abs(a).sum(axis=1)).ravel()
    save_npz('lava-focus/mpm/rebuild-32/suspended-matrix.npz',a)
    print(json.dumps(dict(shape=a.shape,diag=[d.min(),d.max()],zeroRows=int((norm==0).sum()),diagZero=int((d==0).sum()),emptyRows=np.flatnonzero(norm==0)[:30].tolist(),nnz=a.nnz,asymmetry=float(abs(a-a.T).max()))),flush=True)
    raise Captured()
solver.splu=capture
s,c,_=initial()
try:s.step(.001,bed=HotBed(1450.),boundary=c['config'])
except Captured:pass
