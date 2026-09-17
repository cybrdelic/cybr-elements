"""Compare one full step with two half steps from the same accepted state."""
import lava_feed38
import time,json,argparse
import numpy as np
from lava_feed38 import restore_bed
from lava_mpm import MPM,ROOT
from lava_mpm_coupled import snapshot,restore,error_state,temporal_error

p=argparse.ArgumentParser();p.add_argument('--scheme',default='backward_euler');a=p.parse_args()
s=MPM.load(ROOT/'rebuild-38/integrated-flow/frame-05000');s.material.heat_integrator=a.scheme;bed=restore_bed(s.driver_state['bed']);cfg=s.driver_state['config']
s._solve_deadline=time.monotonic()+90;state=snapshot(s,dict(bed=bed));initial=s.time
def step(dt):
    s.step(dt,bed=bed,boundary=cfg);bed.advance(dt)
step(.1);coarse=error_state(s,state[0]);coarse_bed=bed.temperature.copy()
restore(s,dict(bed=bed),state);step(.05);step(.05);fine=error_state(s,state[0])
errors=temporal_error(coarse,fine,s.cell_size)
errors['substrateTemperature']=float(np.max(abs(coarse_bed-bed.temperature)))/.5
report=dict(status='pass' if max(errors.values())<=1 else 'fail',scheme=a.scheme,initialTime=initial,duration=.1,normalizedErrors=errors,
            limits='Local estimate at one cooling state only. It is not whole-sequence temporal or spatial convergence.')
(ROOT/'rebuild-38'/('temporal-'+a.scheme+'-check.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report))
