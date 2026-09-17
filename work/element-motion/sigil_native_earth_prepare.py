"""Pack existing, uncut stone shapes around the approved stroke centerlines."""
from pathlib import Path
import sys,json,numpy as np
from scipy.ndimage import map_coordinates
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent;B=R/'sigil-native';variant=sys.argv[1] if len(sys.argv)>1 else '01';rng=np.random.default_rng(6271+int(variant))
with np.load(B/f'mark-{variant}-motion.npz') as a:P=a['points'];T=a['times'];ids=a['stroke_ids']
T=.15+(T-.15)/(T[-1]-.15)*5.05
with np.load(R/f'sigil-v1/mark-{variant}.npz') as a:sdf=a['sdf']
strokes=[]
for k in np.unique(ids[ids>=0]):
 q=ids==k;p=P[q];t=T[q];d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
 if len(p)>1:strokes.append((p,t,d))
total=sum(d[-1] for p,t,d in strokes);centers=[];radii=[];births=[];starts=[];velocities=[];family=[]
for k,(p,t,d) in enumerate(strokes):
 count=max(3,round(d[-1]/total*900))
 for j in range(count):
  distance=(j+.5)/count*d[-1];index=np.clip(np.searchsorted(d,distance)-1,0,len(p)-2);u=(distance-d[index])/max(1e-9,d[index+1]-d[index]);point=p[index]*(1-u)+p[index+1]*u;born=t[index]*(1-u)+t[index+1]*u
  direction=p[index+1]-p[index];direction/=max(1e-9,np.linalg.norm(direction));normal=np.array([-direction[1],direction[0]])
  wx=point[0]/.82;wz=(point[1]-2.1)/.82+2.95;sd=float(map_coordinates(sdf,[[((wz-2.95)/6.4125+.5)*575],[(wx/11.4+.5)*1023]],order=1)[0])*.82
  radius=rng.uniform(.07,.115) if j%23==0 else rng.uniform(.035,.065) if j%3==0 else min(.034,.010/max(.05,rng.random())**.55)
  radius=min(radius,max(.012,sd*.65));tube=min(.14,max(.035,sd*.60))
  accepted=False
  for attempt in range(100):
   a=rng.uniform(0,2*np.pi);cross=rng.uniform(0,1)**.5*tube;along=rng.uniform(-.025,.025);q=point+normal*np.cos(a)*cross+direction*along;center=np.array([q[0],np.sin(a)*cross,q[1]])
   if not centers or np.all(np.linalg.norm(np.asarray(centers)-center,axis=1)>np.asarray(radii)+radius+.002):accepted=True;break
   if attempt in [35,65,85]:radius*=.8
  if not accepted:continue
  source=np.array([point[0]-direction[0]*.15,-.32,point[1]-direction[1]*.15]);velocity=np.array([direction[0]*1.6,.7,direction[1]*1.6])
  centers.append(center);radii.append(radius);births.append(born);starts.append(source);velocities.append(velocity);family.append(k)
centers=np.asarray(centers);radii=np.asarray(radii);tree=cKDTree(centers);pairs=tree.query_pairs(2*radii.max()+.002,output_type='ndarray');clearance=np.linalg.norm(centers[pairs[:,0]]-centers[pairs[:,1]],axis=1)-radii[pairs[:,0]]-radii[pairs[:,1]];assert not len(clearance) or clearance.min()>.0019
np.savez_compressed(B/f'earth-{variant}-sources.npz',centers=centers,radii=radii,births=births,starts=starts,velocities=velocities,stroke=family)
report=dict(variant=variant,bodies=len(centers),radiusRange=[float(radii.min()),float(radii.max())],minSphereClearance=float(clearance.min()),geometry='Existing accepted convex stones and layered fracture meshes; no glyph-shaped carving',guide='Per-body spring anchors with physical Bullet contacts; constraints disabled at release')
(B/f'earth-{variant}-sources.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
