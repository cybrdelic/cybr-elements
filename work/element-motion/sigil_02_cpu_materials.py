from pathlib import Path
import subprocess,time,json
R=Path(__file__).resolve().parent;O=R/'sigil-02-active-elements';blender='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe';jobs=[]
for kind in ['ice','lava','lightning']:
 log=(O/f'{kind}-cpu-motion.log').open('w',encoding='utf-8');p=subprocess.Popen([blender,'--background','--python',str(R/'sigil_02_new_materials.py'),'--',kind],stdout=log,stderr=subprocess.STDOUT);jobs.append((kind,p,log))
(O/'cpu-material-processes.json').write_text(json.dumps({k:p.pid for k,p,_ in jobs}))
try:
 while any(p.poll() is None for _,p,_ in jobs):
  for kind,p,_ in jobs:
   if p.poll() not in [None,0]:raise RuntimeError(f'{kind} failed: {p.returncode}')
  time.sleep(3)
finally:
 for _,p,l in jobs:
  if p.poll() is None:p.terminate()
  l.close()
print('CPU material sequence gates completed.')
