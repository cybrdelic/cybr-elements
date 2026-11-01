"""Register the original style02 air recipe; never generate copied engines."""
from pathlib import Path
import json
from element_scenes import SCENES
R=Path(__file__).resolve().parent;O=R/'sigil-02-elements'
spec=SCENES['sigil_02_air']
assert spec.tracer_density==.85 and spec.tracer_decay==.65
assert spec.source_asset=='sigil-02-v2/source.npz' and spec.review_gate==135
O.mkdir(exist_ok=True)
(O/'contract.json').write_text(json.dumps({'variant':'02','approvedFire':'../sigil-02-v2/fire-02.mp4',
    'elements':['water','earth','air','lightning'],'nativeFrames':294,'fps':30,'duration':9.8,
    'geometry':'Full approved tapered source, no output-image mask','reviewFrames':[60,135,180,240,293],
    'iterationsPerElement':3,'gpuJobsAtOnce':1,'sourceOwner':'element_scenes.SCENES[sigil_02_air]',
    'solverGenerated':False},indent=2))
print('Original air recipe uses canonical runtime; review contract saved, no solver rewritten.')
