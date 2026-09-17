"""Unique skeleton-edge strokes instead of a double-back DFS traversal."""
from pathlib import Path
import numpy as np,json
from scipy.ndimage import gaussian_filter1d,map_coordinates
from skimage.morphology import skeletonize
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;B=R/'sigil-native'
for variant in ['01','02']:
 D=np.load(R/f'sigil-v1/mark-{variant}.npz');mask=D['mask'];coords=np.argwhere(skeletonize(mask));lookup={tuple(p):i for i,p in enumerate(coords)};adj=[set() for _ in coords]
 for i,(y,x) in enumerate(coords):
  for dy in [-1,0,1]:
   for dx in [-1,0,1]:
    if not (dx or dy):continue
    j=lookup.get((y+dy,x+dx))
    if j is None:continue
    if dx and dy and ((y+dy,x) in lookup or (y,x+dx) in lookup):continue
    adj[i].add(j)
 visited=set();chains=[]
 def edge(a,b):return (min(a,b),max(a,b))
 def walk(i,j):
  chain=[i,j];visited.add(edge(i,j))
  while len(adj[j])==2:
   k=next(k for k in adj[j] if k!=i)
   if edge(j,k) in visited:break
   visited.add(edge(j,k));chain.append(k);i,j=j,k
  return chain
 for i in range(len(coords)):
  if len(adj[i])==2:continue
  for j in sorted(adj[i]):
   if edge(i,j) not in visited:chains.append(walk(i,j))
 for i in range(len(coords)):
  for j in sorted(adj[i]):
   if edge(i,j) not in visited:chains.append(walk(i,j))
 strokes=[]
 for c in chains:
  pix=coords[c]
  if len(pix)<3:continue
  p=np.column_stack(((pix[:,1]/1023-.5)*11.4,2.95+(pix[:,0]/575-.5)*6.4125));p=gaussian_filter1d(p,1.0,axis=0)
  p[:,0]*=.82;p[:,1]=(p[:,1]-2.95)*.82+2.10
  length=np.linalg.norm(np.diff(p,axis=0),axis=1).sum()
  if length<.025:continue
  strokes.append(p)
 # Start left; prefer continuing at the nearest unvisited endpoint.
 remaining=list(range(len(strokes)));ordered=[];tip=np.array([-5,2.1])
 while remaining:
  candidates=[]
  for j in remaining:
   for reverse in [False,True]:
    q=strokes[j][-1 if reverse else 0];cost=np.linalg.norm(q-tip)+max(0,tip[0]-q[0])*.3;candidates.append((cost,j,reverse))
  _,j,reverse=min(candidates);p=strokes[j][::-1] if reverse else strokes[j];ordered.append(p);tip=p[-1];remaining.remove(j)
 points=[];times=[];emits=[];stroke_ids=[];clock=.15
 for k,p in enumerate(ordered):
  if points:
   gap=np.linalg.norm(p[0]-points[-1]);travel=min(.055,.012+gap/100)
   points.extend([points[-1],p[0]]);times.extend([clock,clock+travel]);emits.extend([0,0]);stroke_ids.extend([-1,-1]);clock+=travel
  d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];duration=max(.020,d[-1]/8.5)
  for q,t in zip(p,clock+d/max(d[-1],1e-9)*duration):points.append(q);times.append(t);emits.append(1);stroke_ids.append(k)
  clock+=duration
 points=np.asarray(points);times=np.asarray(times);emits=np.asarray(emits);stroke_ids=np.asarray(stroke_ids)
 # Collapse duplicate timestamps so numerical derivatives remain finite.
 keep=np.r_[np.diff(times)>1e-7,True];points=points[keep];times=times[keep];emits=emits[keep];stroke_ids=stroke_ids[keep]
 np.savez_compressed(B/f'mark-{variant}-motion.npz',points=points,times=times,emit=emits,stroke_ids=stroke_ids)
 im=Image.new('RGB',(1440,810));draw=ImageDraw.Draw(im)
 for k,p in enumerate(ordered):
  q=np.column_stack(((p[:,0]/10.5+.5)*1440,(4.2-p[:,1])/4.2*576+90));draw.line([tuple(v) for v in q],fill=(220,125+(k*17)%90,60+(k*29)%150),width=2)
 im.save(B/f'mark-{variant}-strokes.jpg',quality=94)
 report=dict(variant=variant,strokes=len(strokes),pathLength=float(sum(np.linalg.norm(np.diff(p,axis=0),axis=1).sum() for p in strokes)),writeEnd=float(clock),points=len(points),originalSilhouetteUsedFor='Centerline extraction only; never a render or combustion mask')
 (B/f'mark-{variant}-motion.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
