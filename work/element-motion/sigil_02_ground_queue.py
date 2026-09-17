"""One GPU render at a time; encode and audit both completed sequences."""
from pathlib import Path
import subprocess,time,json,sys
R=Path(__file__).resolve().parent;O=R/'sigil-02-bending-ground'
blender=Path('C:/Program Files/Blender Foundation/Blender 4.5/blender.exe')
def status(stage):
 (O/'STATUS.json').write_text(json.dumps(dict(stage=stage,userAccepted=False,updated=time.time()),indent=2));print(stage,flush=True)
status('Waiting for earth full render')
while not (O/'earth-report.json').exists():time.sleep(4)
assert len(list((O/'earth-frames').glob('*.jpg')))==390
status('Rendering water full resolution')
with (O/'full/render.log').open('w') as log:
 water=subprocess.Popen([str(blender),'--background','--python',str(R/'sigil_02_ground_water_render.py'),'--','--full'],stdout=log,stderr=subprocess.STDOUT)
 subprocess.run([sys.executable,str(R/'sigil_02_ground_finish.py'),'encode','earth'],check=True)
 if water.wait():raise RuntimeError('Water renderer failed; see full/render.log')
status('Encoding and auditing water')
subprocess.run([sys.executable,str(R/'sigil_02_ground_finish.py'),'encode','water'],check=True)
status('Full renders complete; visual review pending')
