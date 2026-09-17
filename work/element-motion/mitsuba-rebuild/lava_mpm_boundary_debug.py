"""Capture an actual failed enriched inlet mapping for a focused regression."""
import json,numpy as np
from lava_mpm import MPM,ROOT
from lava_mpm_continuous import HotBed
import lava_mpm_inlet as inlet

original=inlet.velocity_map
def capture(xyz,dx,labels,config,ground=True,ground_mask=None,cell_size=None):
    try:return original(xyz,dx,labels,config,ground,ground_mask,cell_size)
    except Exception:
        np.savez_compressed(ROOT/'validation'/'inlet-failed-support.npz',xyz=xyz,dx=dx,labels=labels,ground_mask=ground_mask,cell_size=cell_size)
        (ROOT/'validation'/'inlet-failed-support.json').write_text(json.dumps(config))
        raise
inlet.velocity_map=capture
s=MPM.load(ROOT/'continuous-21');setup=json.loads((ROOT/'continuous-21'/'inlet.json').read_text());bed=HotBed(setup['bedTemperatureK'])
for i in range(20):
    if s.time>=setup['nextEmission']-1e-9:inlet.emit(s,setup['config'],setup['period']);setup['nextEmission']+=setup['period']
    step=min(.12,.22/max(np.sum(abs(s.v)/s.cell_size,axis=1).max(),1e-4),.2/max(np.linalg.norm(s.C,axis=(1,2)).max(),1e-4),setup['nextEmission']-s.time)
    r=s.step(step,boundary=setup['config'],bed=bed)
    print(json.dumps(dict(step=i,time=s.time,dt=step,speed=r['maximumSpeed'])),flush=True)
