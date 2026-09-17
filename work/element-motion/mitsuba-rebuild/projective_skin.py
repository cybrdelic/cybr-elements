"""Implicit global/local membrane solve for the material-scale coupon.

The sparse global solve transmits compression across the complete surface.
This replaces local edge sweeps which had collapsed the driven boundary
without compressing the interior. Bending remains a distance approximation.
"""
import numpy as np
from scipy.sparse import coo_matrix,diags
from scipy.sparse.linalg import splu

def solve(x,edges,length,kind,uv,frames=100):
 n=len(x);nedge=len(edges);dt=1/50.;mass=.0025*2700*.74*.38/n;inertia=mass/dt**2;foundation=80.;velocity=np.zeros_like(x);stats=np.zeros((frames,3));state=np.ones(nedge,dtype='i1')
 rows=np.repeat(np.arange(nedge),2);B=coo_matrix((np.tile([1.,-1.],nedge),(rows,edges.ravel())),shape=(nedge,n)).tocsr();weight=np.where(kind==0,2000.,22.);pin=(uv[:,0]<.001)|(uv[:,0]>.739);pin_weight=pin.astype(float)*2e5
 def factor():
  W=diags(weight*state);BT=B.T@W;A=BT@B+diags(np.full(n,inertia+foundation)+pin_weight);return splu(A.tocsc()),BT
 lu,BT=factor();initial=x.copy();max_compression=.29
 for f in range(frames):
  previous=x.copy();progress=min(1.,f/75.);right=.74*(1-max_compression*progress);velocity*=.965;velocity[:,2]-=.25*dt;predicted=x+velocity*dt;target=initial.copy();target[uv[:,0]>.739,0]=right
  # A nonuniform in-plane shear loads the cooled membrane in tension only
  # after its compression folds have formed.
  if f>76:target[uv[:,0]>.739,1]+=.014*(f-76)/23*np.sin(uv[uv[:,0]>.739,1]*12)
  for iteration in range(16):
   d=B@x;distance=np.linalg.norm(d,axis=1);projection=d*(length/np.maximum(distance,1e-12))[:,None];floor=x.copy();floor[:,2]=np.maximum(floor[:,2],.010+.011*np.exp(-(floor[:,1]/.17)**4));rhs=inertia*predicted+BT@projection+foundation*floor+pin_weight[:,None]*target;x=lu.solve(rhs)
  if f>76 and f%6==0:
   strain=np.linalg.norm(B@x,axis=1)/length-1;new=(strain>.055)&(kind==0)&(state==1)
   if new.any():state[new]=0;lu,BT=factor()
  velocity=(x-previous)/dt;stats[f]=[np.linalg.norm(velocity,axis=1).max(),x[:,2].max(),(state==0).sum()]
 return x,velocity,state,stats
