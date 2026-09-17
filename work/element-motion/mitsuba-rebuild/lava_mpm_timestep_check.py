"""Compare a larger implicit advection step with conservative substeps."""
import json,time,numpy as np
from lava_mpm import MPM,ROOT
from lava_mpm_continuous import HotBed
from lava_mpm_inlet import emit

def main():
    folder=ROOT/'continuous-21';runs=[];wall=time.time()
    for safety in (.22,.5):
        gradient_safety=.2 if safety==.22 else .5
        s=MPM.load(folder);setup=json.loads((folder/'inlet.json').read_text());bed=HotBed(setup['bedTemperatureK']);begin=s.time;target=begin+.025;steps=0
        while s.time<target-1e-10:
            if s.time>=setup['nextEmission']-1e-9:emit(s,setup['config'],setup['period']);setup['nextEmission']+=setup['period']
            dt=min(.12,safety/max(np.sum(abs(s.v)/s.cell_size,axis=1).max(),1e-4),gradient_safety/max(np.linalg.norm(s.C,axis=(1,2)).max(),1e-4),target-s.time,setup['nextEmission']-s.time)
            s.step(dt,bed=bed,boundary=setup['config']);steps+=1
        runs.append((s,steps))
    a,b=runs[0][0],runs[1][0]
    velocity=float(np.sqrt(np.sum(a.mass[:,None]*(a.v-b.v)**2)/np.sum(a.mass[:,None]*a.v**2)))
    position=float(np.linalg.norm(a.x-b.x,axis=1).max());thermal=float(abs(a.material.temperature(a.h)-b.material.temperature(b.h)).max())
    passed=velocity<.1 and position<.000025 and thermal<3
    result=dict(status='pass' if passed else 'fail',comparisonStart=begin,duration=.025,cflFactors=[.22,.5],gradientFactors=[.2,.5],steps=[r[1] for r in runs],massWeightedVelocityRelativeError=velocity,maximumPositionDifferenceM=position,maximumTemperatureDifferenceK=thermal,seconds=time.time()-wall,limits='A short exact-state timestep check, not spatial convergence or long-term fracture validation.')
    (ROOT/'validation'/'continuous_timestep.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':main()
