"""Discarded thermal previews must not change an accepted coupled result."""
import lava_feed38
import json,numpy as np
from lava_mpm import MPM,ROOT
from lava_feed38 import restore_bed
from lava_mpm_coupled import advance

results=[]
for enabled in [False,True]:
    s=MPM.load(ROOT/'rebuild-38/adaptive-resume');bed=restore_bed(s.driver_state['bed'])
    r=advance(s,.002,max_dt=.002,max_wall=60,advance_auxiliaries=True,thermal_preflight=enabled,bed=bed,boundary=s.driver_state['config'])
    results.append((s,bed,r))
a,ba,ra=results[0];b,bb,rb=results[1]
errors={k:float(np.max(abs(getattr(a,k)-getattr(b,k)))) for k in ['x','v','h','damage','deviator']}
errors['bedTemperature']=float(np.max(abs(ba.temperature-bb.temperature)))
assert errors['x']<1e-12 and errors['v']<1e-10 and errors['h']<1e-4
assert errors['damage']<1e-10 and errors['deviator']<1e-3 and errors['bedTemperature']<1e-8
assert len(a.rows)==len(b.rows) and abs(a.time-b.time)<1e-12
ledger_error=max(abs(a.ledger.get(k,0)-b.ledger.get(k,0)) for k in a.ledger)
assert ledger_error<1e-8 and abs(ba.received-bb.received)<1e-8
assert ra['accepted']==rb['accepted'] and ra['rejected']==rb['rejected']
report=dict(status='pass',maximumStateDifferences=errors,maximumLedgerDifference=ledger_error,acceptedRowsUnchanged=True,
            bedHeatDifference=abs(ba.received-bb.received),scope='Thermal-preview rollback at the same accepted dt')
(ROOT/'rebuild-38/preflight-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
