"""Measure each constitutive trial in one existing crust state."""
import lava_feed38
import argparse,json,time,numpy as np
from lava_mpm import MPM,ROOT
from lava_feed38 import restore_bed
p=argparse.ArgumentParser();p.add_argument('--dt',type=float,default=.05);p.add_argument('--wall',type=float,default=45);p.add_argument('--acceleration',choices=['anderson','relaxed'],default='anderson');a=p.parse_args()
s=MPM.load(ROOT/'rebuild-38/integrated-flow/frame-05000');bed=restore_bed(s.driver_state['bed'])
s.damage_acceleration=a.acceleration
original=MPM._step;records=[];start=time.monotonic()
def measured(self,dt,**kwargs):
    damage=self.damage.copy();stress=np.log1p(self._creep_stress_guess/1e6);t=time.monotonic()
    row=original(self,dt,**kwargs)
    residual=np.log1p(self._trial_creep_stress/1e6)-stress
    records.append(dict(dt=dt,seconds=time.monotonic()-t,damageError=float(np.max(abs(self.damage-damage))),
                        creepError=float(np.max(abs(residual))),creepNorm=float(np.linalg.norm(residual)),
                        creepIndex=int(np.argmax(abs(residual))),friction=row.get('friction',{})))
    return row
MPM._step=measured;s._solve_deadline=start+a.wall;error=None;row=None
try:row=s.step(a.dt,bed=bed,boundary=s.driver_state['config'])
except Exception as exc:error=repr(exc)
result=dict(error=error,seconds=time.monotonic()-start,dt=a.dt,records=records,row=row)
path=ROOT/'rebuild-38'/('coupling-trace-'+a.acceleration+'-'+str(a.dt)+'.json');path.write_text(json.dumps(result,indent=2))
if error is None:np.savez_compressed(path.with_suffix('.npz'),x=s.x,v=s.v,h=s.h,damage=s.damage,deviator=s.deviator)
print(json.dumps(dict(path=str(path),error=error,seconds=result['seconds'],iterations=len(records))))
