"""Finite rock/lava heat transfer survives a checkpoint continuation."""
import lava_feed38
from lava_feed38 import bed_state,restore_bed
from lava_mpm import MPM,ROOT
import numpy as np,json

s=MPM.load(ROOT/'rebuild-38/finite-bed/frame-00000');bed=restore_bed(s.driver_state['bed']);config=s.driver_state['config']
def advance(s,bed):
    s.step(.1,bed=bed,boundary=config);bed.advance(.1);s.driver_state['bed']=bed_state(bed)
advance(s,bed);folder=ROOT/'rebuild-38/bed-resume-check';s.save(folder)
t=MPM.load(folder);other=restore_bed(t.driver_state['bed'])
advance(s,bed);advance(t,other)
np.testing.assert_allclose(s.x,t.x,rtol=1e-9,atol=1e-11)
np.testing.assert_allclose(s.h,t.h,rtol=1e-10,atol=1e-7)
np.testing.assert_allclose(bed.temperature,other.temperature,rtol=1e-10,atol=1e-7)
assert abs(s.ledger['bed']-bed.received)<1e-10
assert abs(s.time-bed.time)<1e-12
assert bed.temperature.max()>bed.ambient
report=dict(status='pass',resumedPositionErrorM=float(abs(s.x-t.x).max()),
            resumedRockTemperatureErrorK=float(abs(bed.temperature-other.temperature).max()),
            rockEnergyErrorJ=bed.rows[-1]['energyErrorJ'],equalOppositeHeatExchange=True)
(ROOT/'rebuild-38/bed-resume-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
