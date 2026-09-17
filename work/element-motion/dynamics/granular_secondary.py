"""One-way fine debris from exposed, shearing MPM material.
Particles retain identity and inherit carrier velocity; drag depends on size.
"""
from pathlib import Path
import sys,json
import numpy as np
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent
for K in sys.argv[1:] or ['snow','sand']:
    folder=R/'cache'/K;birth=np.load(folder/'static.npz')['birth'];N=len(birth);used=np.zeros(N,dtype=bool);rng=np.random.default_rng(742);x=np.empty((0,3));v=x.copy();rad=np.empty(0);age=np.empty(0);out=folder/'secondary';out.mkdir(exist_ok=True)
    for f in range(120):
        a=np.load(folder/f'{f:04}.npz');p=a['p'];pv=a['v'];ids=np.flatnonzero(birth<float(a['t'])-.07)
        if len(ids)>16:
            dd,nn=cKDTree(p[ids]).query(p[ids],k=9,workers=2);variance=np.linalg.norm(pv[ids]-pv[ids[nn[:,1:]]].mean(1),axis=1)
            surface=dd[:,-1]>(.023 if K=='sand' else .032);score=np.clip(variance/.55,0,1)*surface
            chosen=ids[(rng.random(len(ids))<score*.16)&(~used[ids])];used[chosen]=True;chosen=np.repeat(chosen,3)
            if len(chosen):
                jitter=rng.normal(0,.015,(len(chosen),3));x=np.r_[x,p[chosen]+jitter];v=np.r_[v,pv[chosen]+jitter*12];rad=np.r_[rad,np.clip(.0011/np.maximum(.04,rng.random(len(chosen)))**.4,.0011,.0045)];age=np.r_[age,np.zeros(len(chosen))]
        if len(x):
            for sub in range(4):
                dt=1/120;age+=dt;v[:,2]-=9.81*dt;drag=np.clip(.8*(.002/rad)**1.2,.3,4);v*=np.exp(-dt*drag[:,None]);x+=v*dt
            ok=(age<2.5)&(x[:,2]>-2)&(np.abs(x[:,0])<6);x,v,rad,age=[z[ok] for z in [x,v,rad,age]]
        np.savez_compressed(out/f'{f:04}.npz',p=x.astype('f4'),r=rad.astype('f4'))
    print(K,'secondary frames 120; emitted parents',int(used.sum()),flush=True)
