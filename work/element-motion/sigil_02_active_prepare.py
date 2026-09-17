"""Fresh, bounded revision. Reuse field inputs, never overwrite old caches."""
from pathlib import Path
import json,sys,shutil
R=Path(__file__).resolve().parent
O=R/'sigil-02-active-elements';O.mkdir(exist_ok=True)
for mode in ['cpu','full']:
 base=R/'sigil-02-bending-ground'/mode;out=O/('water-'+mode);out.mkdir(exist_ok=True)
 c=json.loads((base/'config.json').read_text());c.update(frames=240,forceRoot=str(base),sourceRoot=str(base),releaseAt=5.0)
 (out/'config.json').write_text(json.dumps(c,indent=2))
 for n in ['parcels.f32','guides.npz']:
  if not (out/n).exists():(out/n).hardlink_to(base/n)
(O/'plan.json').write_text(json.dumps(dict(scope=['water hold and shedding','ice 02','lava 02','volumetric electricity 02'],protected=['fire','air','earth'],validation='CPU images and motion first; native finite/mass/pressure checks; final decoded film contact sheets and browser',iterations=3,background='black',userAccepted=False),indent=2))
print('Prepared fresh active-elements revision.')
