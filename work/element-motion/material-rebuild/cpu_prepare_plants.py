"""Leaf lag driven by solved stem acceleration, rather than arbitrary sine motion."""
from pathlib import Path
import json,numpy as np
from cpu_material_models import leaf_step
R=Path(__file__).resolve().parent;D=R.parent/'dynamics';a=np.load(D/'cache/plants/rods.npz');info=json.loads((D/'cache/plants/structure.json').read_text());p=a['p'];history=np.zeros((120,len(info['shoots'])),dtype='f4')
for i,row in enumerate(info['shoots']):
 ch=np.array(row['chain']);center=p[:,ch].mean(1);acc=np.gradient(np.gradient(center,axis=0),axis=0)*900;angle=vel=0.
 for f in range(120):
  direction=p[f,ch[-1]]-p[f,ch[0]];side=np.array([-direction[2],0,direction[0]]);side/=max(np.linalg.norm(side),1e-8);target=np.clip(-np.dot(acc[f],side)*.0025,-.35,.35)
  for step in range(8):angle,vel=leaf_step(angle,vel,target,1/240)
  history[f,i]=angle
out=R/'cpu/identity/leaf-lag.npy';np.save(out,history);assert np.isfinite(history).all();print('CPU leaf response',history.shape,'max deflection',round(float(np.abs(history).max()),4))
