"""Persistent ice grains fitted to the existing phase/constraint particle cache."""
from pathlib import Path
import numpy as np,json,sys,time
from scipy.cluster.vq import kmeans2
from scipy.spatial import ConvexHull,cKDTree
R=Path(__file__).resolve().parent;D=R.parent/'dynamics';sys.path.insert(0,str(D));from cache_io import fluid_particles
states=[dict(np.load(D/'cache/ice'/f'{f:04}.npz')) for f in range(120)]
assigned=np.full(len(states[-1]['p']),-1,dtype='i4');groups=[];rng=np.random.default_rng(194)
for frame in range(0,120,3):
 state=states[frame];available=np.flatnonzero((state['phase']>.38)&(assigned[:len(state['p'])]<0))
 if len(available)<6:continue
 tree=cKDTree(state['p'][available])
 for seed in rng.permutation(available):
  if assigned[seed]>=0:continue
  ids=available[tree.query_ball_point(state['p'][seed],.085)];ids=ids[assigned[ids]<0]
  if len(ids)<6:continue
  assigned[ids]=len(groups);groups.append((frame,ids))
parts=[]
for anchor,ids in groups:
 progress=[]
 for state in states:
  live=ids[ids<len(state['p'])];progress.append(float(np.median(state['phase'][live])) if len(live)>.8*len(ids) else 0.)
 x=states[anchor]['p'][ids];center=x.mean(0);local=x-center
 assert np.linalg.norm(local,axis=1).max()<.171,'Nonlocal ice grain rejected before rendering'
 try:hull=ConvexHull(local,qhull_options='QJ')
 except:continue
 vertices=local.copy();faces=hull.simplices.copy();fn=np.cross(vertices[faces[:,1]]-vertices[faces[:,0]],vertices[faces[:,2]]-vertices[faces[:,0]]);wrong=np.sum(fn*hull.equations[:,:3],axis=1)<0;faces[wrong]=faces[wrong][:,[0,2,1]]
 used=np.unique(faces);remap=np.full(len(vertices),-1,dtype='i4');remap[used]=np.arange(len(used));vertices=vertices[used];faces=remap[faces]
 transforms=[]
 for f,state in enumerate(states):
  live=ids<len(state['p']);frac=np.clip((progress[f]-.15)/.50,0,1)
  if live.sum()<8:transforms.append({'active':False});continue
  target=state['p'][ids[live]];cp=target.mean(0);u,_,vh=np.linalg.svd(local[live].T@(target-cp));rot=vh.T@u.T
  if np.linalg.det(rot)<0:vh[-1]*=-1;rot=vh.T@u.T
  transforms.append({'active':bool(frac>.02),'position':cp.tolist(),'rotation':rot.tolist(),'solidFraction':float(frac)})
 parts.append({'vertices':(vertices*.985).tolist(),'faces':faces.tolist(),'anchor':anchor,'members':ids.tolist(),'bubbles':(local[rng.choice(len(local),min(6,len(local)),replace=False)]*.55).tolist(),'transforms':transforms})
(R/'ice-grains.json').write_text(json.dumps({'parts':parts,'maximumGrainRadius':max(np.linalg.norm(np.array(p['vertices']),axis=1).max() for p in parts),'source':'Existing cooling and brittle-constraint particle cache','method':'Local clusters formed when particles freeze; persistent convex boundaries, rigid best-fit motion and phase-controlled growth','limits':'Visual grain reconstruction; inter-grain motion is inherited from the existing particle solve, not a new rigid-body contact simulation'},separators=(',',':')))
print('Persistent ice grains',len(parts),flush=True)
