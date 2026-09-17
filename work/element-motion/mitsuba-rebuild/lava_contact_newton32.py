"""Semismooth Newton for the same non-associated Coulomb fixed point."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
import numpy as np
from scipy.linalg import solve
import time,json

def residual(H,q,mu,p,jacobian=False):
    m=len(mu);n=3*m;ids=np.arange(m)*3;ti=ids[:,None]+[1,2]
    rho_n=1/np.maximum(H.diagonal()[ids],1e-30)
    rho_t=1/np.maximum(np.maximum(H.diagonal()[ids+1],H.diagonal()[ids+2]),1e-30)
    g=(q-H@p).reshape(m,3);v=p.reshape(m,3);r=np.empty_like(v)
    active=v[:,0]+rho_n*g[:,0]>0
    r[:,0]=np.where(active,-g[:,0],v[:,0]/rho_n)
    y=v[:,1:]+rho_t[:,None]*g[:,1:];length=np.linalg.norm(y,axis=1)
    radius=mu*np.maximum(v[:,0],0);slip=length>radius
    direction=y/np.maximum(length[:,None],1e-300)
    projection=y*np.minimum(1,radius/np.maximum(length,1e-300))[:,None]
    r[:,1:]=(v[:,1:]-projection)/rho_t[:,None]
    if not jacobian:return r.ravel()
    J=H.copy()
    for i in np.flatnonzero(~active):
        j=ids[i];J[j]=0;J[j,j]=1/rho_n[i]
    for i in np.flatnonzero(slip):
        rows=ti[i];d=direction[i];R=np.eye(2)-np.outer(d,d)
        I=np.zeros((2,n));I[np.arange(2),rows]=1
        a=radius[i]/max(length[i],1e-300)
        J[rows]=(I-a*R@I)/rho_t[i]+a*R@H[rows]
        if v[i,0]>0:J[rows,ids[i]]-=mu[i]*d/rho_t[i]
    return r.ravel(),J

def newton(H,q,mu,p,iterations=25,deadline=None):
    reports=[]
    for k in range(iterations):
        if deadline is not None and time.monotonic()>deadline:break
        r,J=residual(H,q,mu,p,True);norm=np.linalg.norm(r);maximum=float(abs(r).max())
        reports.append(dict(iteration=k,residual=maximum,norm=float(norm)))
        if maximum<1e-9:break
        J.flat[::len(J)+1]+=H.diagonal()*1e-11
        try:delta=solve(J,-r,check_finite=False,assume_a='gen')
        except Exception:break
        alpha=1.
        for _ in range(24):
            trial=p+alpha*delta
            if np.linalg.norm(residual(H,q,mu,trial))<norm*(1-1e-4*alpha):break
            alpha*=.5
        else:break
        p=trial
    return p,reports

if __name__=='__main__':
    from lava_mpm_friction import _sweeps
    from pathlib import Path
    a=np.load('lava-focus/mpm/rebuild-32/contact-system.npz');H=a['H'];q=a['q'];mu=a['mu']
    p=np.zeros(len(q));g=q.copy();start=time.monotonic();_sweeps(H,mu,p,g,100)
    p,rows=newton(H,q,mu,p);g=q-H@p;error=_sweeps(H,mu,p,g,0)
    result=dict(seconds=time.monotonic()-start,naturalResidual=float(error),iterations=rows)
    Path('lava-focus/mpm/rebuild-32/newton-contact-proof.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)
