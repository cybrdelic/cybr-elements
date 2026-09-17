"""Reduced cohesive grain solve; external bending support ends before collapse.

Persistent local fracture geometry comes from the cooling cache. Grain centers
have mass, gravity, contact and brittle distance bonds. This is a reduced XPBD
model, with spherical contact proxies, not a full rigid fracture solver.
"""
from pathlib import Path
import json,numpy as np
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent
data=json.loads((R/'ice-grains.json').read_text());parts=data['parts'];N=len(parts)
birth=np.array([p['anchor'] for p in parts]);origin=np.array([p['transforms'][p['anchor']].get('position',[0,0,0]) for p in parts]);rot=np.array([p['transforms'][p['anchor']].get('rotation',np.eye(3).tolist()) for p in parts])
radius=np.array([np.linalg.norm(np.array(p['vertices']),axis=1).mean() for p in parts]);mass=np.maximum(radius**3,1e-6);inv=1/mass
eligible=(birth<=57)&(origin[:,2]>.10)
x=origin.copy();v=np.zeros_like(x);pairs=[];lengths=[];alive=[];hist=[];fraction=[];rng=np.random.default_rng(308)
for f in range(120):
 active=eligible&(birth<=f)
 new=np.flatnonzero(active&(birth==f))
 if len(new):
  ids=np.flatnonzero(active);tree=cKDTree(x[ids])
  for i in new:
   for j0 in tree.query_ball_point(x[i],radius[i]*2.7):
    j=int(ids[j0]);distance=np.linalg.norm(x[i]-x[j])
    if i==j or (birth[j]==f and j>i) or distance>1.6*(radius[i]+radius[j]):continue
    pairs.append((i,j));lengths.append(distance);alive.append(True)
 a=np.array(pairs,dtype='i4').reshape(-1,2);rest=np.array(lengths);live=np.array(alive)
 for sub in range(8):
  dt=1/240;t=(f+sub/8)/30;old=x.copy();support=np.clip((2.32-t)/.28,0,1)
  # Support is an explicit external bending force, gradually released. Gravity
  # and fracture determine the subsequent breakup; visibility never fades.
  force=np.zeros_like(x);force[:,2]=-9.81*(1-support)
  force+=(origin-x)*(support*45)-v*(support*8+.10)
  v[active]+=force[active]*dt;x[active]+=v[active]*dt
  for iteration in range(5):
   if len(a):
    delta=x[a[:,1]]-x[a[:,0]];distance=np.maximum(np.linalg.norm(delta,axis=1),1e-8)
    live&=(distance<rest*1.48+.007)
    ii,jj=a[live].T;d=delta[live];ll=distance[live];err=ll-rest[live]
    compliance=2e-7/(dt*dt);corr=d*(err/ll/(inv[ii]+inv[jj]+compliance))[:,None]
    np.add.at(x,ii,corr*inv[ii,None]);np.add.at(x,jj,-corr*inv[jj,None])
   floor=radius*.7;x[active,2]=np.maximum(x[active,2],floor[active])
  v[active]=(x[active]-old[active])/dt
  grounded=active&(x[:,2]<radius*.7+.0001);v[grounded,:2]*=.88
  if sub==7:
   ids=np.flatnonzero(active);contacts=cKDTree(x[ids]).query_pairs(float(radius.max()*1.8),output_type='ndarray')
   if len(contacts):
    ii,jj=ids[contacts[:,0]],ids[contacts[:,1]];d=x[jj]-x[ii];ll=np.maximum(np.linalg.norm(d,axis=1),1e-8);depth=(radius[ii]+radius[jj])*.66-ll;ok=depth>0
    corr=d[ok]*(depth[ok]/ll[ok]*.15)[:,None];np.add.at(x,ii[ok],-corr);np.add.at(x,jj[ok],corr)
 alive=live.tolist();hist.append(x.copy());fraction.append(np.clip((f-birth+1)/7,0,1)*active)
 assert np.isfinite(x).all()
np.savez_compressed(R/'ice-cohesion.npz',p=np.array(hist,dtype='f4'),rotation=rot.astype('f4'),fraction=np.array(fraction,dtype='f4'))
(R/'ice-cohesion.json').write_text(json.dumps({'grains':int(eligible.sum()),'bonds':len(pairs),'intactAtEnd':sum(alive),'substeps':8,'constraintIterations':5,'supportRelease':[2.04,2.32],'method':__doc__},indent=2))
print('Cohesive ice',int(eligible.sum()),'grains',len(pairs),'bonds',flush=True)
