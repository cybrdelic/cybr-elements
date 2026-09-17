"""Profile a single saved state without changing the cache."""
import json,cProfile,pstats,io
from lava_mpm import MPM,ROOT
from lava_mpm_continuous import HotBed
from lava_mpm_inlet import emit
s=MPM.load(ROOT/'continuous-21');setup=json.loads((ROOT/'continuous-21'/'inlet.json').read_text())
if s.time>=setup['nextEmission']-1e-9:emit(s,setup['config'],setup['period'])
profile=cProfile.Profile();profile.enable();s.step(.004,bed=HotBed(setup['bedTemperatureK']),boundary=setup['config']);profile.disable()
output=io.StringIO();pstats.Stats(profile,stream=output).sort_stats('cumulative').print_stats(18)
path=ROOT/'validation'/'step-profile.txt';path.write_text(output.getvalue());print(output.getvalue())
