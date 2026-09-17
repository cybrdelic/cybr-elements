import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',LAVA_MPM_LINEAR_BACKEND=os.environ.get('LAVA_PROBE_BACKEND','cpu'),LAVA_MPM_FRICTION_BACKEND='cpu',LAVA_MPM_PRESSURE_WARM_START='1',LAVA_MPM_ACTIVE_FRICTION='1')
from lava_mpm import MPM,ROOT
from lava_mpm_inlet import emit
from lava_mpm_reservoir import HotBed
from lava_mpm_sparse_pressure import STATS
from lava_mpm_linear27 import metrics
from pathlib import Path
import json,time
s=MPM.load(ROOT/'rebuild-33/suspended-warm-pressure/frame-0800')
c=json.loads((ROOT/'rebuild-33/suspended-warm-pressure/setup.json').read_text())['config']
emit(s,c,.1);start=time.monotonic();s._solve_deadline=start+100
try:
    row=s.step(.1,bed=HotBed(1450.),boundary=c)
    r=dict(status='pass',time=s.time,seconds=time.monotonic()-start,pressure=STATS,row=row)
except Exception as e:r=dict(status='fail',error=repr(e),seconds=time.monotonic()-start,pressure=STATS)
r['linearBackend']=metrics()
(ROOT/'rebuild-32'/('scene-pressure-'+os.environ['LAVA_MPM_LINEAR_BACKEND']+'-proof.json')).write_text(json.dumps(r,indent=2));print(json.dumps(r),flush=True)
