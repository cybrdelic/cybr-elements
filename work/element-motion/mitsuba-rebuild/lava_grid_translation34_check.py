"""World grid translation must preserve inlet/ground topology and free DOFs."""
import numpy as np,json
from pathlib import Path
from lava_mpm import ground_map
from lava_mpm_inlet import velocity_map
from lava_mpm_suspended34 import initial
from lava_mpm import basis,mechanical_fields,p2g
cell=np.full(3,.01);shape=np.array([7,7,9]);origin=np.array([-.10,-.03,-.02])
xyz=origin+np.array(np.unravel_index(np.arange(np.prod(shape)),shape)).T*cell
config=dict(plane=-.08,half_width=.015,height=.025,peak_speed=.08)
labels=np.zeros(len(xyz),int);S,b=velocity_map(xyz,.01,labels,config)
shift=np.array([.005,0,0]);S2,b2=velocity_map(xyz+shift,.01,labels,dict(config,plane=config['plane']+shift[0]))
assert S.shape==S2.shape and (S-S2).nnz==0 and np.max(abs(b-b2))<1e-12
G=ground_map(xyz,.01);G2=ground_map(xyz+[.005,.005,0],.01)
assert G.shape==G2.shape and (G-G2).nnz==0
s,c,_=initial();ids,w,g,dp=basis(s.x,s.dx,s.origin,s.shape)
tags=np.zeros_like(ids);grid,fields,local=mechanical_fields(ids,tags)
xx=s.origin+np.array(np.unravel_index(grid,s.shape)).T*s.cell_size
P,lift=velocity_map(xx,s.dx,fields,c['config'],False,cell_size=s.cell_size)
empty=int((np.asarray(abs(P).sum(axis=0)).ravel()==0).sum())
assert empty==0,empty
r=dict(status='pass',translatedInletIdentical=True,translatedGroundIdentical=True,suspendedEmptyColumns=empty,suspendedDofs=P.shape[1])
Path('lava-focus/mpm/rebuild-32/grid-translation-proof.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
