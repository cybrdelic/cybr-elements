from pathlib import Path
import subprocess,time,json,sys,shutil,hashlib
R=Path(__file__).resolve().parent;O=R/'sigil-02-active-elements';blender='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
# One GPU renderer at a time: overlapping jobs throttled this laptop.
while not (O/'water-audit.json').exists():time.sleep(5)
for kind in ['lightning','lava','ice']:
 audit=O/f'{kind}-audit.json';movie=O/f'{kind}-candidate.mp4'
 if audit.exists() and movie.exists():
  a=json.loads(audit.read_text())
  if a['decodedFrames']==300 and a['sha256']==hashlib.sha256(movie.read_bytes()).hexdigest():
   print('Reusing completed verified film',kind,flush=True);continue
 gate=O/kind/'production-gate.json'
 while not gate.exists():time.sleep(3)
 assert json.loads(gate.read_text())['cpuReviewed']
 assert shutil.disk_usage(O).free>65*2**20
 with (O/f'{kind}-full.log').open('w',encoding='utf-8') as log:
  p=subprocess.Popen([blender,'--factory-startup','--background','--python',str(R/'sigil_02_new_materials.py'),'--',kind,'--full'],stdout=log,stderr=subprocess.STDOUT)
  (O/'material-process.json').write_text(json.dumps(dict(kind=kind,pid=p.pid,sourceSha256=hashlib.sha256((R/'sigil_02_new_materials.py').read_bytes()).hexdigest())))
  while p.poll() is None:
   if shutil.disk_usage(O).free<35*2**20:p.terminate();raise RuntimeError('Stopped before disk exhaustion')
   time.sleep(3)
  assert p.returncode==0
 subprocess.run([sys.executable,str(R/'sigil_02_active_finish.py'),'encode',kind],check=True)
print('All material films encoded and audited. Publication still requires visual review.',flush=True)
