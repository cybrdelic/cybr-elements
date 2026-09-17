"""Replay the inlet/ground corner that failed when its crust fractured."""
import json,numpy as np
from lava_mpm import ROOT
from lava_mpm_inlet import velocity_map

def main():
    folder=ROOT/'validation';a=np.load(folder/'inlet-failed-support.npz');cfg=json.loads((folder/'inlet-failed-support.json').read_text())
    S,lift=velocity_map(a['xyz'],float(a['dx']),a['labels'],cfg,True,a['ground_mask'],a['cell_size'])
    assert np.isfinite(S.data).all() and np.isfinite(lift).all()
    rng=np.random.default_rng(71);u=(S@rng.normal(size=S.shape[1])+lift).reshape(-1,3)
    xyz=a['xyz'];labels=a['labels'];cell=a['cell_size']
    # This exact field had a free upstream ghost but a bonded downstream
    # mirror. Both must share the same corner boundary condition.
    i=np.flatnonzero((abs(xyz-[-.028,0,-.0005]).max(1)<1e-10)&(labels==42))[0]
    target=np.array([-.02,0,.0005]);j=np.flatnonzero((abs(xyz-target).max(1)<1e-10)&(labels==42))[0]
    from lava_mpm_inlet import profile
    expected=u[j]-np.array([2*float(profile(0,.0005,cfg)),0,0])
    error=float(abs(u[i]-expected).max());assert error<1e-12,error
    out=dict(status='pass',fixtureNodes=len(xyz),degreesOfFreedom=S.shape[1],reflectedCornerVelocityError=error,limits='Exact failed boundary fixture and affine ghost composition; not a flow convergence test.')
    (folder/'fractured_inlet_boundary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))

if __name__=='__main__':main()
