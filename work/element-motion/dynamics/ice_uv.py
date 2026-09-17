"""Advect ice texture coordinates with persistent liquid particle identities."""
import sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from cache_io import fluid_particles
out=R/'cache/ice-uv';out.mkdir(exist_ok=True);rest=np.empty((0,3))
for f in range(120):
    q,_=fluid_particles(f);rest=np.r_[rest,q[len(rest):]];state=np.load(R/'cache/ice'/f'{f:04}.npz');surface=np.load(R/'surface/ice'/f'{f:04}.npz');v=surface['v']
    if len(v):
        d,i=cKDTree(state['p']).query(v,k=4);w=1/np.maximum(d,.005)**3;w/=w.sum(1)[:,None];uv=np.sum(rest[i][:,:,[0,2]]*w[:,:,None],axis=1)*.48
    else:uv=np.empty((0,2))
    np.savez_compressed(out/f'{f:04}.npz',uv=uv.astype('f4'))
print('Ice UV: 120 frames, persistent material coordinates')
