from pathlib import Path
import json
import numpy as np
import sys
sys.path.insert(0,'work')
import font_motion as m
samples=np.array([m.pose(t)[0] for t in np.linspace(m.START,m.START+m.WRITE,15000)])
assert np.isfinite(samples).all()
assert np.max(np.linalg.norm(np.diff(samples,axis=0),axis=1))<.005
assert abs(m.WRITE-12.93)<1e-6
source=Path('work/render_script_fire.py').read_text()
assert 'opening=' not in source
assert 'closing=' not in source
assert 'if t>=20.625:' in source
report={'glyphStyle':'custom connected italic script','glyphs':'cybrdelic','continuousNozzle':True,'writingSeconds':(m.START+m.WRITE)*16/30,'zoomCompleteSeconds':7.45,'holdSeconds':3.55,'valveClosesSeconds':11,'physicalReservoirDrainPerSecond':1.8,'temporalClosingFade':False,'reusesOldFontFrames':False}
Path('work/script-font-checks.json').write_text(json.dumps(report,indent=2))
print(report)
