"""Sparse passive spray: born only at fast, locally stretching free surfaces."""
import numpy as np
from scipy.spatial import cKDTree
from mesh_repair import DiffuseWhitewater
class SelectiveSpray(DiffuseWhitewater):
 def step(self,p,v,field,vel,spacing,h,dt,iso,extent,obstacles,enabled=True):
  super().step(p,v,field,vel,spacing,h,dt,iso,extent,obstacles,enabled)
  born=np.flatnonzero(self.age==0)
  if len(born):
   tree=cKDTree(p);_,nearest=tree.query(self.p[born]);base=p[nearest];speed=np.linalg.norm(v[nearest],axis=1)
   _,nb=tree.query(base,k=min(12,len(p)));delta=p[nb]-base[:,None,:];relative=v[nb]-v[nearest,None,:];stretch=np.max(np.sum(delta*relative,axis=2)/np.maximum(np.sum(delta**2,axis=2),1e-8),axis=1)
   eligible=(speed>1.0)&(stretch>4)&(self.mode[born]==1)&(self.rng.random(len(born))<.35)
   keep=np.ones(len(self.p),bool);keep[born[~eligible]]=False;self.total_births-=int(np.sum(~eligible))
   for key in ['p','v','radius','life','life0','age','mode']:setattr(self,key,getattr(self,key)[keep])
   fresh=self.age==0;n=int(fresh.sum());u=self.rng.random(n);self.radius[fresh]=h*.025*(1-u*(1-(.12/.025)**-1.8))**(-1/1.8)
   life=self.rng.uniform(.3,.65,n);self.life[fresh]=life;self.life0[fresh]=life
  if not len(self.p):return np.empty((0,6),np.float32)
  fade=np.minimum(1,self.life/.15)*np.minimum(1,(self.age+dt)/.07)
  return np.column_stack([self.p,self.radius,self.mode,fade]).astype(np.float32)
