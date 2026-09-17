"""Capture the actual cooled-crust friction bottleneck for CPU/GPU comparison."""
import lava_feed38
import json,numpy as np
from scipy.sparse import save_npz
from lava_mpm import ROOT,MPM
from lava_feed38 import restore_bed
import lava_mpm_friction as friction

folder=ROOT/'rebuild-38/friction-system';folder.mkdir(exist_ok=True)
s=MPM.load(ROOT/'rebuild-38/integrated-flow/frame-05000');bed=restore_bed(s.driver_state['bed'])
class Captured(BaseException):pass
def capture(A,rhs,S,C,compliance,offset=None,friction=None,tangent_offset=None,deadline=None,initial_impulse=None):
    for name,value in [('A',A),('S',S),('C',C)]:save_npz(folder/(name+'.npz'),value)
    values=dict(rhs=rhs,compliance=compliance,offset=offset,friction=friction,tangent_offset=tangent_offset)
    if initial_impulse is not None:values['initial_impulse']=initial_impulse
    np.savez_compressed(folder/'vectors.npz',**values)
    print(json.dumps(dict(dofs=A.shape[0],contacts=C.shape[0],folder=str(folder))));raise Captured
friction.contact=capture
try:s.step(.05,bed=bed,boundary=s.driver_state['config'])
except Captured:pass
