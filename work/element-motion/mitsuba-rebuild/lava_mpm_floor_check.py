"""Rigid-body trajectory near the floor, with and without impact."""
import json,numpy as np
from lava_mpm import MPM,ROOT,block

def main():
    s=MPM(block([-.01,-.01,.01],[.01,.01,.03],.005),.005,.01,temperature=900.)
    x=s.x.copy();dt=.02;expected=np.array([0.,0.,-9.81*dt])
    s.step(dt,thermal=False)
    velocity=float(np.max(np.linalg.norm(s.v-expected,axis=1)))
    position=float(np.max(np.linalg.norm(s.x-x-dt*expected,axis=1)))
    assert velocity<1e-5 and position<1e-6,(velocity,position)
    # Several implicit steps bring the finite particle domains into contact.
    minimum=1.
    for _ in range(5):
        s.step(.02,thermal=False)
        minimum=min(minimum,float((s.x[:,2]-.5*np.cbrt(s.volume)).min()))
        assert minimum>-1e-5,minimum
    gap=s.x[:,2]-.5*np.cbrt(s.volume)
    assert gap.min()>-1e-5,float(gap.min())
    result=dict(status='pass',freeFallVelocityErrorMPerS=velocity,freeFallPositionErrorM=position,minimumDomainGroundGapM=minimum,floorImpulseNs=s.ledger.get('solid_floor_impulse_norm',0.),limits='Rigid translation and coarse-domain nonpenetration checked at every step; solid ground contact is normal-only, not a validated frictional collision law.')
    (ROOT/'validation'/'solid_floor_contact.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':main()
