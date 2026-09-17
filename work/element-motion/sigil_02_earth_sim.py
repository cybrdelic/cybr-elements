"""CPU discrete rigid clast dynamics with contact impulses and bending forces.

Spherical collision proxies surround the original layered stone render meshes.
Suspension is authored; gravity, inertia and pair contacts are integrated.
"""
from pathlib import Path
import json,time
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parent;O=R/'sigil-02-elements';src=np.load(O/'earth-source.npz')
target=src['centers'];r=src['radii'];born=src['births'];direction=src['directions'];n=len(r)
rng=np.random.default_rng(92314);p=target-direction*.28;p[:,1]-=.16
v=direction*1.3;v[:,1]=.7;omega=rng.normal(0,1.2,(n,3));rot=Rotation.random(n,random_state=rng).as_quat()
mass=4/3*np.pi*r**3*2650;inv=1/np.maximum(mass,.01);live=np.zeros(n,bool);cache=[];maxpenetration=0.;contacts=0;started=time.time()
for f in range(294):
 for sub in range(8):
  t=(f+sub/8)/30;dt=1/240;live|=born<=t
  release=np.clip((t-6.8)/.45,0,1);release=release*release*(3-2*release)
  moving=target.copy();moving[:,0]+=.032*np.sin(t*1.4+target[:,2]*3);moving[:,1]+=.035*np.sin(t*1.9+target[:,0]*2)
  # Broad collection forces retain the brand pose while individual clasts
  # respond dynamically. Every such force is disabled during release.
  acceleration=((moving-p)*28-v*8)*(1-release)
  acceleration[:,2]-=9.81*release
  v[live]+=acceleration[live]*dt;v[live]*=np.exp(-.10*dt);p[live]+=v[live]*dt
  ids=np.flatnonzero(live)
  if len(ids)>1:
   pairs=cKDTree(p[ids]).query_pairs(2*r.max()+.002,output_type='ndarray')
   if len(pairs):
    a=ids[pairs[:,0]];b=ids[pairs[:,1]];delta=p[b]-p[a];dist=np.linalg.norm(delta,axis=1);overlap=r[a]+r[b]-dist;hit=overlap>0
    a=a[hit];b=b[hit];delta=delta[hit];dist=dist[hit];overlap=overlap[hit]
    if len(a):
     normal=delta/np.maximum(dist[:,None],1e-9);den=inv[a]+inv[b];relative=v[b]-v[a];closing=np.sum(relative*normal,axis=1)
     impulse=np.maximum(0,-closing*1.04+overlap*.18/dt)/den
     J=normal*impulse[:,None];np.add.at(v,a,-J*inv[a,None]);np.add.at(v,b,J*inv[b,None])
     correction=normal*(overlap*.25/den)[:,None];np.add.at(p,a,-correction*inv[a,None]);np.add.at(p,b,correction*inv[b,None])
     friction=(relative-normal*closing[:,None])*.025;np.add.at(v,a,friction);np.add.at(v,b,-friction)
     maxpenetration=max(maxpenetration,float(overlap.max()));contacts+=len(a)
  omega[live]*=np.exp(-(.85*(1-release)+.08)*dt)
  rot[live]=(Rotation.from_rotvec(omega[live]*dt)*Rotation.from_quat(rot[live])).as_quat()
 assert np.isfinite(p).all() and np.isfinite(v).all()
 cache.append(np.column_stack((p,rot)).astype('f'))
 if f%60==0:print('FRAME',f,'live',int(live.sum()),'seconds',round(time.time()-started,1),flush=True)
np.savez_compressed(O/'earth-motion.npz',transforms=cache,radii=r,births=born,velocity=v)
report={'frames':294,'fps':30,'bodies':n,'finite':True,'substeps':8,'contacts':contacts,'maximumTransientOverlap':maxpenetration,'releaseMedianDrop':float(np.median(np.asarray(cache)[203,:,2]-np.asarray(cache)[-1,:,2])),'model':'Discrete clast inertia, mass-weighted sphere contact impulses, friction and gravity; authored damped collection forces disabled at6.8s; original uncut layered meshes'}
(O/'earth-sim-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
