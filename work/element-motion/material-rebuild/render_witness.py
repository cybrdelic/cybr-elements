"""Air phenomena seen through fine matter responding to different forces."""
from pathlib import Path
import sys,numpy as np,bpy
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from common import *
K=sys.argv[sys.argv.index('--kind')+1];a=np.load(R/'cpu/witness'/f'{K}.npz');s=setup();s.view_settings.exposure=.4
mats=[scene.material('Illuminated fine dust '+str(i),(.30,.33,.36),.52) for i in range(3)]
for i,m in enumerate(mats):m.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value=.02;m.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value=(.5,.6,.7,1)
for f in selected():
 p=a['p'][f];r=a['r'];dis=a['displacement'][f];speed=a['speed'][f]
 # The same fixed witness particles persist. Brightness follows local light
 # and motion exposure, not a painted ring or a particle birth/death mask.
 fixed=(np.arange(len(p))%4==0);active=(dis>.0008 if K=='sound' else dis>.01)|fixed
 q=p[active];rr=r[active];instance('Fine pressure witness',q,rr,mats[1],subdivision=1)
 if f:
  vel=(p-a['p'][f-1])*30;ids=np.flatnonzero(active&(speed>.15));paths=[np.array([p[i]-vel[i]/180,p[i]]) for i in ids]
  if paths:scene.curve('Resolved witness exposure',paths,r[ids]*.6,mats[1])
 finish(s,K,f)
