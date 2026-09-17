"""Hierarchical 3D discharge paths derived from the approved 02 medial graph.
The sigil is an authored electric attraction field, not a plasma prediction.
"""
from pathlib import Path
import numpy as np,json
from scipy.ndimage import distance_transform_edt
from skimage.morphology import skeletonize
R=Path(__file__).resolve().parent;O=R/'sigil-02-active-elements/lightning';O.mkdir(parents=True,exist_ok=True)
s=np.load(R/'sigil-02-v2/source.npz');sk=skeletonize(s['sdf']>.006);pixels=set(map(tuple,np.argwhere(sk)));adj={p:[(p[0]+a,p[1]+b) for a,b in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)] if (p[0]+a,p[1]+b) in pixels] for p in pixels}
used=set();paths=[]
for start in sorted(pixels,key=lambda p:len(adj[p])==2):
 for nxt in adj[start]:
  if tuple(sorted([start,nxt])) in used:continue
  path=[start,nxt];used.add(tuple(sorted([start,nxt])))
  while len(adj[nxt])==2:
   follow=[p for p in adj[nxt] if p!=path[-2]][0];edge=tuple(sorted([nxt,follow]))
   if edge in used:break
   used.add(edge);path.append(follow);nxt=follow
  if len(path)>4:
   pp=np.array(path);x=s['lo'][0]+pp[:,1]/(sk.shape[1]-1)*s['extent'][0];z=s['lo'][2]+pp[:,0]/(sk.shape[0]-1)*s['extent'][2]
   xyz=np.column_stack([x,.12*np.sin(x*2.3),z]);paths.append(xyz)
rng=np.random.default_rng(51097);families=[]
for family in range(9):
 segments=[]
 for k,path in enumerate(paths):
  q=path[::2].copy()
  if len(q)<3:continue
  noise=rng.normal(0,.012,q.shape);noise[[0,-1]]=0;q+=noise;q[:,1]+=.075*np.sin(np.arange(len(q))*.48+family+k)
  strength=.65+rng.random()*.35;segments.append(dict(points=q.tolist(),radius=.0045,power=strength,group=k%6))
  for j in range(3,len(q)-3,max(5,len(q)//3)):
   if rng.random()>.55:continue
   root=q[j];direction=rng.normal(size=3);direction[1]*=.6;direction/=np.linalg.norm(direction);length=rng.uniform(.15,.65)
   branch=[root.copy()]
   for n in range(1,8):branch.append(root+direction*length*n/7+rng.normal(0,.035,3)*(n/7))
   segments.append(dict(points=np.array(branch).tolist(),radius=.0018,power=.24,group=k%6))
 families.append(segments)
(O/'channels.json').write_text(json.dumps(dict(families=families,source='Approved 02 skeleton, recursively forked 3D channels; stochastic event trains, retained return-stroke channels',paths=len(paths))))
print('Electric graph',len(paths),'main paths / 9 independent discharge families')
