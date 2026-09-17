"""Coherent separation of the original sigil as a resolved luminous membrane."""
from pathlib import Path
import sys,re,xml.etree.ElementTree as ET,numpy as np,bpy
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from common import *
sys.path.insert(0,str(R.parent));from shared_motion import pose
s=setup();s.view_settings.exposure=-.7;scene.glare(s,2,-.97)
base=np.load(R/'cpu/identity/projection.npz')['base'];rng=np.random.default_rng(141)
base[:,1]=rng.normal(0,.003,len(base));radius=rng.uniform(.0007,.0016,len(base));level=rng.choice(4,len(base),p=[.55,.30,.12,.03]);mats=[scene.emission('Coherent projected identity '+str(i),(.07,.68,.40),v) for i,v in enumerate([.6,1.4,3.5,10])];source_mat=scene.emission('Source identity membrane',(.018,.17,.13),1.8);threads=scene.emission('Connecting field filaments',(.035,.31,.23),1.7)
objects=[]
for f in selected():
 for ob in objects:scene.remove(ob)
 objects=[];t=(f+1)/30
 if t>.08:
  p,_,_,_=pose(min(t,1.68));source=np.array([-3.58,0,1.1]);dest=np.array([p[0],-.07,p[1]]);energy=np.exp(-max(0,t-2.1)*1.8)
  objects.append(instance('Persistent source sigil',base[::3]+source,radius[::3]*.6*energy,source_mat,subdivision=1))
  # All points retain the original local silhouette. Only the membrane depth
  # moves; no font is substituted and no identity is melted into liquid.
  ghost=base+dest;ghost[:,1]+=.017*np.sin(base[:,0]*15+t*3)*np.sin(np.clip((t-.08)/1.6,0,1)*np.pi)
  for i,mat in enumerate(mats):
   ok=level==i;objects.append(instance('Projected coherent membrane '+str(i),ghost[ok],radius[ok]*energy,mat,subdivision=1))
  if t<2.65:
   paths=[];rr=[]
   for i in range(0,len(base),max(1,len(base)//110)):
    u=np.linspace(0,1,34);path=source[None]*(1-u[:,None])+dest[None]*u[:,None]+base[i]
    path[:,1]+=.07*np.sin(u*np.pi)*np.sin(u*12+base[i,0]*10-t*2);paths.append(path);rr.append(.00038*energy*np.sin(u*np.pi)**.7)
   objects.append(scene.curve('Fine continuity between source and projection',paths,rr,threads))
 finish(s,'spirit-projection',f)
