import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import numpy as np,json
from scipy.sparse import csr_matrix,eye
from lava_mpm_sparse_pressure import contact,_WARM
from pathlib import Path
rows=[]
for seed in range(6):
    rng=np.random.default_rng(770+seed);n=42;Q,_=np.linalg.qr(rng.normal(size=(n,n)))
    A=csr_matrix(Q@np.diag(np.geomspace(1,1e4,n))@Q.T);C=csr_matrix(rng.normal(size=(60,n)));S=eye(n,format='csr')
    b=rng.normal(size=n);offset=rng.normal(size=60)*.001;comp=np.full(60,1e-4)
    os.environ['LAVA_MPM_PRESSURE_WARM_START']='1';_WARM.clear();contact(A,b,S,C,comp,offset)
    b2=b+rng.normal(size=n)*1e-3;warm=contact(A,b2,S,C,comp,offset)
    os.environ['LAVA_MPM_PRESSURE_WARM_START']='0';cold=contact(A,b2,S,C,comp,offset)
    err=float(np.max(abs(warm[0]-cold[0])))
    assert err<1e-7,(seed,err)
    rows.append(dict(seed=seed,velocityError=err,warmIterations=warm[4],coldIterations=cold[4],residual=warm[1]))
r=dict(status='pass',cases=rows);Path('lava-focus/mpm/rebuild-32/pressure-warm-proof.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
