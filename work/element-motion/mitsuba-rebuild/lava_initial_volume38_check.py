"""Initial boundary mass versus an independent vertical-column integral."""
import json
import numpy as np
from lava_mpm import ROOT
n=1024;x=-.012+(np.arange(n)+.5)*.024/n;y=-.009+(np.arange(n)+.5)*.018/n
x,y=np.meshgrid(x,y,indexing='ij');r=1-(x/.012)**2-(y/.009)**2
dz=.006*np.sqrt(np.maximum(r,0));valid=(r>0)&(x>=-.006)
hi=np.where(valid,.0045+dz,0);lo=np.where(valid,np.maximum(0,.0045-dz),0)
pipe=(x<-.0045)&(abs(y)<.003)
height=np.where(pipe,np.maximum(.006,hi),hi-lo)
reference=float(height.sum()*.024*.018/n**2);rows=[]
for name in ['hot-nozzle','integrated-coarse','nozzle-fine','integrated-fine']:
    s=np.load(ROOT/'rebuild-38'/name/'frame-00000/state.npz');volume=float(s['volume'].sum())
    rows.append(dict(case=name,relativeVolumeError=abs(volume-reference)/reference,volumeM3=volume))
assert rows[1]['relativeVolumeError']<.001 and rows[3]['relativeVolumeError']<.001
assert rows[1]['relativeVolumeError']<rows[0]['relativeVolumeError']
assert rows[3]['relativeVolumeError']<rows[2]['relativeVolumeError']
report=dict(status='pass',referenceVolumeM3=reference,cases=rows,reference='1024 squared vertical-column integration of the continuous union')
(ROOT/'rebuild-38/initial-volume-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
