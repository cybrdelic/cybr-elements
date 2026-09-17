from pathlib import Path
import numpy as np,json
from scipy.spatial import HalfspaceIntersection,ConvexHull
R=Path(__file__).resolve().parent;rng=np.random.default_rng(8124);center=np.array([0,0,.78]);axes=np.array([1.45,.62,.78]);seeds=[]
while len(seeds)<65:
 p=rng.uniform(-1,1,3)
 if (p*p).sum()>.86:continue
 p=p*axes+center
 if seeds and min(np.linalg.norm(p-q) for q in seeds)<.20:continue
 seeds.append(p)
seeds=np.array(seeds);directions=rng.normal(size=(100,3));directions/=np.linalg.norm(directions,axis=1)[:,None]
outer=np.c_[directions/axes,-1-(directions/axes)@center];pieces=[]
for i,p in enumerate(seeds):
 others=np.delete(seeds,i,axis=0);diff=others-p;planes=np.c_[2*diff,(p*p).sum()-(others*others).sum(1)];vertices=HalfspaceIntersection(np.r_[planes,outer],p).intersections;hull=ConvexHull(vertices);faces=hull.simplices.copy()
 for j,f in enumerate(faces):
  v=vertices[f]
  if np.dot(np.cross(v[1]-v[0],v[2]-v[0]),hull.equations[j,:3])<0:faces[j]=f[::-1]
 origin=vertices.mean(0);pieces.append({'verts':(vertices-origin).tolist(),'faces':faces.tolist(),'center':origin.tolist(),'volume':hull.volume})
links=[]
for i in range(len(pieces)):
 for j in range(i):
  if np.linalg.norm(seeds[i]-seeds[j])<.52:links.append([i,j])
(R/'earth-geometry.json').write_text(json.dumps({'pieces':pieces,'links':links}));print(len(pieces),'volumetric fragments',len(links),'candidate connections')
