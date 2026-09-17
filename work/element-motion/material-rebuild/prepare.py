"""Material coordinates and surface-attached detail from existing dynamics caches."""
from pathlib import Path
import sys,json,time
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
R=Path(__file__).resolve().parent;D=R.parent/'dynamics';sys.path.insert(0,str(D))
from cache_io import fluid_particles,fluid_mesh
kinds=sys.argv[1:] or ['lava','ice','foam']
for kind in kinds:
 out=R/'data'/kind;out.mkdir(parents=True,exist_ok=True);rest=np.empty((0,3));start=time.time()
 for f in range(120):
  if kind in ['lava','ice']:
   q,_=fluid_particles(f,kind=='lava');rest=np.r_[rest,q[len(rest):]]
   a=np.load(D/'surface'/kind/f'{f:04}.npz');state=np.load(D/'cache'/kind/f'{f:04}.npz');v=a['v'];fa=a['f']
   if len(v):
    d,ix=cKDTree(state['p']).query(v,k=min(4,len(state['p'])),workers=2);w=1/np.maximum(d,.008)**3;w/=w.sum(1)[:,None];coord=(rest[ix]*w[:,:,None]).sum(1)
   else:coord=np.empty((0,3))
   innerfaces=fa
   if kind=='ice' and len(v):
    ed=np.concatenate([fa[:,[0,1]],fa[:,[1,2]],fa[:,[2,0]]]);graph=coo_matrix((np.ones(len(ed)),(ed[:,0],ed[:,1])),shape=(len(v),len(v)))
    _,labels=connected_components(graph,directed=False);major=np.argmax(np.bincount(labels));innerfaces=fa[labels[fa[:,0]]==major]
   np.savez_compressed(out/f'{f:04}.npz',v=v,f=fa,heat=a['heat'],phase=a['phase'],coord=coord.astype('f4'),innerfaces=innerfaces)
  else:
   v,fa,_,_=fluid_mesh(f);a=np.load(D/'cache/foam'/f'{f:04}.npz');p=a['p'];rad=a['r'];film=a['film'];ids=a['id']
   if len(v) and len(p):
    ds,ix=cKDTree(v).query(p,workers=2);keep=(film>.18)&(ds<.07);p=p[keep];rad=rad[keep];film=film[keep];ids=ids[keep];ix=ix[keep]
    normal=np.zeros_like(v);fn=np.cross(v[fa[:,1]]-v[fa[:,0]],v[fa[:,2]]-v[fa[:,0]])
    for j in range(3):np.add.at(normal,fa[:,j],fn)
    normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-8)
    signed=np.sum((p-v[ix])*normal[ix],axis=1)
    p=p-normal[ix]*signed[:,None]+normal[ix]*(rad*.3+.004)[:,None]
    if len(p):dd,near=cKDTree(p).query(v,workers=2);coverage=np.exp(-(dd/.039)**2)*film[near]
    else:coverage=np.zeros(len(v))
   else:p=np.empty((0,3));rad=film=ids=np.empty(0);coverage=np.zeros(len(v));normal=np.zeros_like(v)
   np.savez_compressed(out/f'{f:04}.npz',v=v,f=fa,normal=normal,coverage=coverage,p=p,r=rad,film=film,id=ids)
 print(kind,'120 prepared frames',round(time.time()-start,1),'seconds',flush=True)
