"""Compare sparse/dense contact on the actual newly solidifying lava state."""
import json,time,numpy as np
from lava_mpm import MPM,ROOT
from lava_mpm_continuous import HotBed

def main():
    folder=ROOT/'continuous-19';setup=json.loads((folder/'inlet.json').read_text());states=[];times=[]
    for kind in ('dense','admm'):
        s=MPM.load(folder);s.contact_solver=kind;start=time.time();s.step(.012,boundary=setup['config'],bed=HotBed(setup['bedTemperatureK']));times.append(time.time()-start);states.append(s)
    velocity=float(np.linalg.norm(states[0].v-states[1].v,axis=1).max());position=float(np.linalg.norm(states[0].x-states[1].x,axis=1).max());heat=float(abs(states[0].h-states[1].h).max())
    assert velocity<1e-5 and position<1e-6,(velocity,position)
    result=dict(status='pass',velocityErrorMPerS=velocity,positionErrorM=position,enthalpyErrorJPerKg=heat,denseSeconds=times[0],sparseSeconds=times[1],sourceTime=states[0].time-.012,limits='One matched real-scene step; not a long trajectory equivalence or spatial convergence test.')
    (ROOT/'validation'/'sparse_contact_scene.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':main()
