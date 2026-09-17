"""Capture one failed-resolution pressure system without advancing the cache."""
import lava_feed38
import json
from pathlib import Path
import numpy as np
from scipy.sparse import save_npz
from lava_mpm import MPM,ROOT
from lava_mpm_inlet import emit
from lava_mpm_reservoir import HotBed
import lava_mpm_sparse_pressure as pressure

folder=ROOT/'rebuild-38/pressure-system';folder.mkdir(exist_ok=True)
s=MPM.load(ROOT/'rebuild-38/nozzle-fine/frame-01500');config=s.driver_state['config']
if s.time>=s.driver_state['nextEmission']-1e-9:emit(s,config,.5)
class Captured(BaseException):pass
def capture(A,rhs,S,C,compliance,offset=None,**kwargs):
    for name,value in [('A',A),('S',S),('C',C)]:save_npz(folder/(name+'.npz'),value)
    np.savez_compressed(folder/'vectors.npz',rhs=rhs,compliance=compliance,offset=offset)
    (folder/'source.json').write_text(json.dumps(dict(time=s.time,dt=.2,particles=len(s.x),dofs=A.shape[0],constraints=C.shape[0])))
    raise Captured
pressure.contact=capture
try:s.step(.2,boundary=config,bed=HotBed(1450.))
except Captured:print(str(folder))
