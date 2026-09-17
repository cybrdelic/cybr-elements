"""Benchmark the same cooled-crust contact equations on CPU and CUDA."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',CUDA_VISIBLE_DEVICES='0',LAVA_MPM_CONTACT_ACCELERATION='anderson')
import time,json,numpy as np
from scipy.sparse import load_npz
from lava_mpm import ROOT
from lava_mpm_friction import contact
from lava_mpm_linear27 import cuda_runtime
from lava_mpm_cuda_contact27 import metrics

folder=ROOT/'rebuild-38/friction-system';v=dict(np.load(folder/'vectors.npz'));A=load_npz(folder/'A.npz');S=load_npz(folder/'S.npz');C=load_npz(folder/'C.npz');rows=[]
for backend in ['cpu','cuda_batched']:
    os.environ['LAVA_MPM_FRICTION_BACKEND']=backend
    if backend=='cuda_batched':torch=cuda_runtime();torch.ones(1,device='cuda').sum().item();torch.cuda.synchronize()
    before=metrics();start=time.monotonic();r=contact(A,S=S,C=C,deadline=start+60,**v);elapsed=time.monotonic()-start;after=metrics()
    if backend=='cpu':reference=r[0]
    error=float(np.linalg.norm(r[0]-reference)/max(np.linalg.norm(reference),1e-30));assert error<1e-5
    rows.append(dict(backend=backend,seconds=elapsed,velocityDifference=error,residual=r[1],gpuFactors=after['gpuFactors']-before['gpuFactors'],fallbacks=after['fallbacks']))
report=dict(status='pass',cases=rows,selected='cuda_batched' if rows[1]['gpuFactors']>0 and rows[1]['seconds']<rows[0]['seconds']*.8 else 'cpu')
(ROOT/'rebuild-38/friction-backend-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
