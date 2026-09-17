"""CPU/CUDA comparison on identical captured equations, excluding warmup."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',CUDA_VISIBLE_DEVICES='0',LAVA_MPM_PRESSURE_LINESEARCH='exact',LAVA_MPM_PRESSURE_WARM_START='0')
import time,json,numpy as np
from scipy.sparse import load_npz
from lava_mpm import ROOT
from lava_mpm_sparse_pressure import contact,_WARM
from lava_mpm_linear27 import cuda_runtime,metrics

folder=ROOT/'rebuild-38/pressure-system';v=dict(np.load(folder/'vectors.npz'))
A=load_npz(folder/'A.npz');S=load_npz(folder/'S.npz');C=load_npz(folder/'C.npz');rows=[]
for backend in ['cpu','cuda_dense']:
    os.environ['LAVA_MPM_LINEAR_BACKEND']=backend;warmup=0.
    if backend=='cuda_dense':
        start=time.monotonic();torch=cuda_runtime();torch.ones(1,device='cuda').sum().item();torch.cuda.synchronize();warmup=time.monotonic()-start
    _WARM.clear();before=metrics();start=time.monotonic()
    r=contact(A,v['rhs'],S,C,v['compliance'],v['offset'],deadline=start+60)
    elapsed=time.monotonic()-start;after=metrics()
    if backend=='cpu':reference=r[0]
    error=float(np.linalg.norm(r[0]-reference)/max(np.linalg.norm(reference),1e-30))
    assert error<1e-6 and r[1]<2e-8
    rows.append(dict(backend=backend,seconds=elapsed,warmupSeconds=warmup,residual=r[1],velocityRelativeDifference=error,
                     gpuFactors=after['gpuFactors']-before['gpuFactors'],fallbacks=after['fallbacks']))
report=dict(status='pass',cases=rows,selected='cuda_dense' if rows[1]['gpuFactors']>0 and rows[1]['seconds']<rows[0]['seconds']*.8 else 'cpu')
(ROOT/'rebuild-38/backend-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
