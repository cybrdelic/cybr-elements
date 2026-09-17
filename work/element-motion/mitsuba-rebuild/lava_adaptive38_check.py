"""The known inaccurate interval must be subdivided before acceptance."""
import lava_feed38
import json,time
from lava_mpm import MPM,ROOT
from lava_feed38 import restore_bed
from lava_mpm_coupled import advance
s=MPM.load(ROOT/'rebuild-38/integrated-flow/frame-05000');bed=restore_bed(s.driver_state['bed']);start=time.monotonic()
try:
    report=advance(s,.1,max_dt=.1,max_wall=180,advance_auxiliaries=True,bed=bed,boundary=s.driver_state['config'])
except Exception as exc:
    result=dict(status='incomplete',error=repr(exc),lastAcceptedTime=s.time,targetTime=5.1,
                report=getattr(s,'_adaptive_report',{}),scope='Cooled-crust adaptive test did not complete')
    (ROOT/'rebuild-38/adaptive-check.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='report'}));raise SystemExit(1)
assert report['rejected']>=1
assert abs(s.time-5.1)<1e-10 and abs(bed.time-s.time)<1e-10
assert all(max(r['errors'].values())<=1 for r in report['records'])
result=dict(status='pass',rejectedInaccurateInterval=True,acceptedSmallerIntervals=report['accepted'],
            maximumAcceptedNormalizedError=max(max(r['errors'].values()) for r in report['records']),
            report=report,wallSeconds=time.monotonic()-start,scope='Local adaptive interval; not whole-sequence or spatial convergence')
(ROOT/'rebuild-38/adaptive-check.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='report'}))
