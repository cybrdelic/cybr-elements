"""Resolved tracer histories: distinct field topology, with shutter-sized dust.

Spirit and energy are designed fictional light phenomena. The trajectories
come from integrated forces; neither is presented as a calibrated EM solver.
"""
from pathlib import Path
import sys,numpy as np,bpy
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from common import *
K=sys.argv[sys.argv.index('--kind')+1];s=setup();s.view_settings.exposure=-.8
a=np.load(D/'cache'/K/'tracers.npz');P=a['p'];E=a['energy'];rad=a['r'];tag=a['tag'];birth=a['birth'];N=len(rad);rng=np.random.default_rng(935)
colors={'energy':[(.055,.20,1),(1,.38,.045)],'spirit':[(.045,.72,.38),(.35,.09,.85)],'flight':[(.62,.68,.72)]}[K]
mats=[]
for j,c in enumerate(colors):
 for level in range(4):
  mat=scene.material(K+' optical level '+str(j)+' '+str(level),c,.24,metal=.05)
  if K!='flight':
   p=mat.node_tree.nodes['Principled BSDF'];p.inputs['Emission Color'].default_value=(*c,1);p.inputs['Emission Strength'].default_value=[.9,2.4,6,16][level]
  mats.append(mat)
if K!='flight':scene.glare(s,2,-.97)
brightness=rng.choice(4,N,p=[.48,.31,.17,.04]);scale=rng.lognormal(-.3,.5,N)
objects=[]
for f in selected():
 for ob in objects:scene.remove(ob)
 objects=[];t=(f+1)/30;live=(E[f]>.025)&(P[f,:,2]>-2)
 if K=='flight':
  # Dust integrates over 1/180 second. Large dots and uniform one-frame sticks
  # were making the old wake look like a wire brush.
  ids=np.flatnonzero(live&(E[max(0,f-1)]>.025));vel=(P[f,ids]-P[max(0,f-1),ids])*30
  widths=np.clip(rad[ids]*.22*scale[ids],.00020,.0016)
  p=P[f,ids];objects.append(instance('Fine illuminated wake dust',p,widths,mats[0],subdivision=1))
  sel=np.linalg.norm(vel,axis=1)>.4;paths=[np.array([pp-vv/180,pp]) for pp,vv in zip(p[sel],vel[sel])]
  objects.append(scene.curve('Velocity-dependent dust exposure',paths,widths[sel]*.6,mats[0]))
 else:
  # Resolve current field bundles across persistent birth cohorts. Joining
  # thousands of individual past trajectories was drawing a mat of hair.
  for group in range(2):
   group_ids=np.flatnonzero(live&(tag==group));group_ids=group_ids[np.argsort(birth[group_ids])]
   strand_count=12 if K=='spirit' else 18
   for strand in range(strand_count):
    ids=group_ids[strand::strand_count]
    if len(ids)<8:continue
    path=P[f,ids].copy();age=np.maximum(0,t-birth[ids]);kernel=np.array([1,2,3,2,1],dtype=float)/9
    smooth=np.column_stack([np.convolve(np.pad(path[:,j],(2,2),mode='edge'),kernel,mode='valid') for j in range(3)])
    if K=='spirit':
     coherence=1-np.exp(-age*4);path=path*(1-coherence[:,None])+smooth*coherence[:,None];level=1 if strand%5 else 2;strength=.45+.35*np.exp(-((age-.22)/.12)**2)
    else:
     path=smooth;phase=age*10+group*np.pi;strength=.18+.82*(.5+.5*np.cos(phase))**4;level=2 if strand%4 else 3
    radius=(.0010+.0005*(strand%3))*strength*np.minimum(1,np.arange(len(ids))/5)*np.minimum(1,(len(ids)-1-np.arange(len(ids)))/5)
    objects.append(scene.curve('Coherent '+K+' field bundle', [path],[radius],mats[group*4+level]))
  finish(s,K,f)
  continue

 finish(s,K,f)
