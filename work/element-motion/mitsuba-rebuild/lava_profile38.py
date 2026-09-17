"""Bounded profile of the unresolved cooled-crust interval; no rendering."""
import lava_feed38
import cProfile,json,pstats,time
from lava_mpm import MPM,ROOT
from lava_feed38 import restore_bed
from lava_mpm_coupled import advance

folder=ROOT/'rebuild-38'
s=MPM.load(folder/'integrated-flow/frame-05000')
bed=restore_bed(s.driver_state['bed'])
profile=cProfile.Profile();start=time.monotonic();error=None
try:
    profile.enable()
    report=advance(s,.1,max_dt=.1,max_wall=30,advance_auxiliaries=True,bed=bed,boundary=s.driver_state['config'])
except Exception as exc:
    error=repr(exc);report=getattr(s,'_adaptive_report',{})
finally:
    profile.disable()
    profile.dump_stats(str(folder/'cooled-profile.pstats'))
    with (folder/'cooled-profile.txt').open('w') as stream:
        pstats.Stats(profile,stream=stream).strip_dirs().sort_stats('cumulative').print_stats(35)
    result=dict(wallSeconds=time.monotonic()-start,time=s.time,error=error,report=report)
    (folder/'cooled-profile.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='report'}))
