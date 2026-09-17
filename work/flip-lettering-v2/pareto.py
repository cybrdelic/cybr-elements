"""Volume-preserving, art-directed subgrid breakup with stable tracked partitions."""
import numpy as np
from scipy.spatial import cKDTree
class ParetoBreakup:
 def __init__(self):self.previous=None;self.ids=np.empty(0,int);self.nextid=0;self.patterns={}
 def apply(self,p,r,v,dt):
  ids=np.full(len(p),-1,int)
  if self.previous is not None and len(self.previous):
   distance,nearest=cKDTree(self.previous).query(p);used=set()
   for k in np.argsort(distance):
    if distance[k]<.035 and int(nearest[k]) not in used:ids[k]=self.ids[nearest[k]];used.add(int(nearest[k]))
  for k in np.flatnonzero(ids<0):ids[k]=self.nextid;self.nextid+=1
  ps=[];rs=[]
  for k,key in enumerate(ids):
   key=int(key)
   if key not in self.patterns:
    rng=np.random.default_rng(91013+key);n=24;u=(np.arange(n)+rng.random(n))/n;rng.shuffle(u);alpha=1.5;ratio=10
    raw=(1-u*(1-ratio**(-alpha)))**(-1/alpha);weights=raw/(np.sum(raw**3)**(1/3));offset=rng.normal(size=(n,3));offset-=np.sum(offset*weights[:,None]**3,axis=0);self.patterns[key]=(weights,offset,0.)
   weights,offset,age=self.patterns[key];age+=dt;self.patterns[key]=(weights,offset,age);rr=r[k]*weights;pos=p[k]+offset*(r[k]*1.5+min(age,.8)*.12);pos[:,1]=np.maximum(pos[:,1],rr+.003);ps.append(pos);rs.append(rr)
  self.previous=p+v*dt;self.ids=ids
  if not len(p):return p.copy(),r.copy(),0.
  resultp=np.concatenate(ps).astype('float32');resultr=np.concatenate(rs).astype('float32');error=float(abs(np.sum(resultr.astype('float64')**3)-np.sum(r.astype('float64')**3))/max(1e-15,np.sum(r.astype('float64')**3)))
  alive=set(map(int,ids));self.patterns={k:x for k,x in self.patterns.items() if k in alive}
  return resultp,resultr,error
