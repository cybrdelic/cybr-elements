"""Compare active friction with the unreduced solve under changing loads."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',LAVA_MPM_CONTACT_ACCELERATION='anderson')
import numpy as np,json
from pathlib import Path
from scipy.sparse import csr_matrix,eye,vstack
from lava_mpm_friction import contact
from lava_mpm_active_contact33 import mixed_contact

rows=[]
for seed in range(8):
    rng=np.random.default_rng(1500+seed);n=24;M=rng.normal(size=(n,n));A=csr_matrix(M.T@M+np.eye(n)*4)
    normals=np.zeros((8,n))
    for i in range(8):
        d=rng.normal(size=3);d/=np.linalg.norm(d);normals[i,3*i:3*i+3]=d
    C=vstack([csr_matrix(normals),csr_matrix(rng.normal(size=(35,n))*.12)],format='csr')
    comp=np.r_[np.full(8,1e-6),np.full(35,.025)];mu=np.r_[rng.uniform(.2,.8,8),np.zeros(35)];offset=rng.normal(size=43)*.03
    for load in range(2):
        rhs=rng.normal(size=n);to=np.zeros(86);S=eye(n,format='csr')
        ref=contact(A,rhs,S,C,comp,offset,mu,to)
        ans=mixed_contact(A,rhs,S,C,comp,offset,mu,to,8)
        err=float(np.max(abs(ref[0]-ans[0])))
        assert err<1e-6,(seed,load,err)
        assert ans[-1]['stationarity']<1e-5
        rows.append(dict(seed=seed,load=load,velocityError=err,activeFriction=ans[-1]['frictionRows'],candidates=8,outer=ans[-1]['pressureActiveIterations']))
result=dict(status='pass',cases=rows,maximumVelocityDifference=max(r['velocityError'] for r in rows))
Path('lava-focus/mpm/rebuild-32/active-contact-proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
