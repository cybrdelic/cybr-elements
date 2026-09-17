"""Render only the corrected earth handoff/release after water frees the GPU."""
from pathlib import Path
import subprocess,time,json,sys
R=Path(__file__).resolve().parent;O=R/'sigil-02-bending-ground';blender=Path('C:/Program Files/Blender Foundation/Blender 4.5/blender.exe')
while not (O/'water-audit.json').exists():time.sleep(4)
source=O/'earth-frames';previous=O/'earth-before-contact-handoff';previous.mkdir(exist_ok=True)
for f in range(226,390):
 p=(source/f'{f:04}.jpg').resolve();q=(previous/p.name).resolve();assert p.parent==source.resolve() and q.parent==previous.resolve()
 if p.exists():p.replace(q)
for name in ['earth-candidate.mp4','earth-audit.json','earth-report.json']:
 p=(O/name).resolve();q=(previous/name).resolve();assert p.parent==O.resolve() and q.parent==previous.resolve()
 if p.exists():p.replace(q)
(O/'STATUS.json').write_text(json.dumps(dict(stage='Rendering corrected earth contact handoff',userAccepted=False),indent=2))
with (O/'earth-contact-full.log').open('w') as log:
 subprocess.run([str(blender),'--background','--python',str(R/'sigil_02_ground_earth_render.py'),'--','--full'],stdout=log,stderr=subprocess.STDOUT,check=True)
subprocess.run([sys.executable,str(R/'sigil_02_ground_finish.py'),'encode','earth'],check=True)
(O/'STATUS.json').write_text(json.dumps(dict(stage='Both final candidates complete; final visual review pending',userAccepted=False),indent=2))
print('Corrected earth contact render and encode complete.',flush=True)
