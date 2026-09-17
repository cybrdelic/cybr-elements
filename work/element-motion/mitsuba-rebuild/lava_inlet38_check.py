"""Finite pipe-mouth collision and unresolved-source regression cases."""
import numpy as np,json
from lava_mpm_inlet import conduit_constraints,conduit_gap,emit
from lava_mpm import MPM,block,ROOT
cfg=dict(plane=-.012,half_width=.003,height=.006,peak_speed=.0004,temperature=1450.,pipe_end=-.006)
# A material point outside the opening, approaching the downstream face.
x=np.array([[-.0059,.004,.003]]);v=np.array([[-.01,0,0]])
local=np.zeros((1,27),int);w=np.full((1,27),1/27)
C,b=conduit_constraints(x,v,local,w,1,.003,.1,cfg)
assert C.shape[0]==1 and np.max(C@v.ravel()-b)>0
stopped=np.array([[-.001,0,0]])
assert np.max(C@stopped.ravel()-b)<1e-12
assert abs(float(conduit_gap(x+.1*stopped,cfg)[0]))<1e-12
# The finite wall ends at the mouth. Recover a small edge penetration in
# the nearest normal direction instead of extending an infinite side plane.
corner=np.array([[-.0061,.0038,.003]])
C,b=conduit_constraints(corner,np.zeros((1,3)),local,w,1,.003,.1,cfg)
assert C.shape[0]==1 and abs(float(C[0,0])+1)<1e-12
recovered=corner+np.array([[.0001,0,0]])
assert conduit_gap(recovered,cfg)[0]>=-1e-12
# Source whose height contains no nonzero velocity basis samples.
s=MPM(block([0,0,0],[.003,.003,.003],.0015),.0015,.003,ground=False)
old=s.rest.copy();oldmass=s.mass.copy();bad=dict(cfg,half_width=.0015,height=.003)
try:emit(s,bad,.5);raise AssertionError('Unresolved inlet was accepted')
except ValueError:pass
assert np.array_equal(old,s.rest) and np.array_equal(oldmass,s.mass)
r=dict(status='pass',pipeEndFaceBlocksBackwardPenetration=True,finiteMouthCornerRecovery=True,unresolvedSourceRejectedWithoutStateMutation=True)
(ROOT/'rebuild-38/inlet-check.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
