"""CPU reconstruction checks: no surface jump merely on crystallization."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import json
import numpy as np
from lava_mpm import MPM,ROOT,block
from lava_mpm_surface import extract,reference_coordinates
folder=ROOT/'rebuild-25/surface-validation';folder.mkdir(exist_ok=True,parents=True)
x=block([-.002,-.002,0],[.002,.002,.002],.0005)
s=MPM(x,.0005,.001,temperature=1450.);s.save(folder/'molten')
a=np.load(extract(folder/'molten/state.npz'));v=a['v'].copy();f=a['f'].copy()
s.h[:]=s.material.enthalpy(950.);s.connectivity.frozen[:]=True;s.save(folder/'coherent')
b=np.load(extract(folder/'coherent/state.npz'))
assert np.array_equal(v,b['v']) and np.array_equal(f,b['f'])
receipt=json.loads((folder/'coherent/state-surface.json').read_text());assert receipt['relativeVolumeDifference']<.001
angle=.64;R=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1.]])@np.diag([1.2,.8,1.1]);shift=np.array([.01,-.007,.002])
state=dict(x=x@R.T+shift,rest=x,F=np.broadcast_to(R,(len(x),3,3)))
points=np.array([[.00031,.00027,.0009],[-.0013,.0006,.0015]])
mapped,_=reference_coordinates(points@R.T+shift,state,np.array([.001]*3));error=float(np.max(abs(mapped-points)));assert error<1e-12
result=dict(status='pass',unchangedSurfaceAtSolidification=True,relativeVolumeDifference=receipt['relativeVolumeDifference'],affineMaterialCoordinateErrorM=error,limits='Unfractured reconstruction only; this does not validate separated large-deformation fracture surfacing.')
(folder/'proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
