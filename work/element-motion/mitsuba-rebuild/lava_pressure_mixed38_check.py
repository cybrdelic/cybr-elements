"""Mixed Newton directions versus independent dense linear algebra."""
import os,json
import numpy as np
from scipy.sparse import csr_matrix,eye
from lava_mpm_sparse_pressure import mixed_direction,contact,_WARM
from lava_mpm import ROOT

rng=np.random.default_rng(38);records=[]
for ratio in [1.,1e2,1e4]:
    n=32;k=13;R=rng.normal(size=(n,n));A=R.T@R+np.eye(n)
    C=rng.normal(size=(k,n))*np.geomspace(1,ratio,k)[:,None]
    comp=np.full(k,.1);g=rng.normal(size=n)
    d=mixed_direction(csr_matrix(A),csr_matrix(C),comp,g)
    exact=np.linalg.solve(A+C.T@np.diag(1/comp)@C,-g)
    err=float(np.linalg.norm(d-exact)/np.linalg.norm(exact))
    assert err<1e-6,(ratio,err)
    records.append(dict(constraintScale=ratio,relativeDirectionError=err))
for mode in ['primal','mixed']:
    os.environ['LAVA_MPM_PRESSURE_NEWTON']=mode;_WARM.clear()
    r=contact(csr_matrix(A),-g,eye(n,format='csr'),csr_matrix(C/1e4),comp,np.zeros(k))
    if mode=='primal':reference=r[0]
    else:np.testing.assert_allclose(r[0],reference,rtol=1e-6,atol=1e-8)
report=dict(status='pass',directionCases=records,complementarityResidual=r[1])
(ROOT/'rebuild-38/mixed-pressure-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
