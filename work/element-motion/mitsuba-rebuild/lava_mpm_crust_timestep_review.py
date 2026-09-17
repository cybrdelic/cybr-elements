"""Compare existing equal-duration CPU runs; never rerender to hide a failure."""
import json
import numpy as np
from lava_mpm import ROOT


def main():
    names=['upper-crust-load-23','upper-crust-load-23-fine']
    states=[np.load(ROOT/name/'state.npz') for name in names]
    proofs=[json.loads((ROOT/name/'proof.json').read_text()) for name in names]
    a,b=states;assert abs(float(a['time'])-float(b['time']))<1e-12
    mass=a['mass'];dv=a['v']-b['v']
    velocity=float(np.sqrt(np.sum(mass[:,None]*dv*dv)/max(np.sum(mass[:,None]*b['v']**2),1e-30)))
    displacement=float(np.linalg.norm(a['x']-b['x'],axis=1).max())
    work=[p['boundaryWorkJ'] for p in proofs];work_error=abs(work[0]-work[1])/max(abs(work[1]),1e-30)
    temperature=float(np.max(abs(a['temperature']-b['temperature'])))
    gates=dict(velocity=velocity<.1,position=displacement<25e-6,loadingWork=work_error<.1,temperature=temperature<3)
    result=dict(status='pass' if all(gates.values()) else 'fail',runs=names,time=float(a['time']),
        maxDtSeconds=[.02,.01],gates=gates,massWeightedVelocityRelativeDifference=velocity,
        maximumPositionDifferenceM=displacement,boundaryWorkJ=work,boundaryWorkRelativeDifference=work_error,
        maximumTemperatureDifferenceK=temperature,
        meaning='Both runs form and export upper-crust fractures. Their trajectories/loading work must also converge; mechanism success alone is insufficient.',
        disposition='Production render blocked until fracture time integration is resolved. No final simulation is claimed.')
    (ROOT/'validation/upper_crust_timestep.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':main()
