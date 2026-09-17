"""Freeze the visually compared 64-sample Cycles variant without changing active jobs."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent
source=(R/'render.py').read_text()
balanced=source.replace('s.cycles.samples=96 if K not in','s.cycles.samples=64 if K not in').replace("dependencyNames=['render.py'","dependencyNames=['render-balanced.py'")
assert source!=balanced
(R/'render-balanced.py').write_text(balanced,encoding='utf-8')
(R/'sample-budget-review.json').write_text(json.dumps({'baselineSha256':hashlib.sha256((R/'render.py').read_bytes()).hexdigest(),'balancedSha256':hashlib.sha256((R/'render-balanced.py').read_bytes()).hexdigest(),'samples':64,'materials':['ice','foam','lava','mud','blood','crystal'],'review':'Compared 96 and 64 sample full frames and original-pixel detail crops at frame 240. Surface texture, bubbles, wet highlights and crystal reflections retained. The lower 32-sample glass trial lost detail and was rejected. Ongoing glass renders retain 96 samples. Native 1920 by 1080, 30 fps, 450 frames retained.'},indent=2))
print('Frozen 64-sample renderer for six compared material families')
