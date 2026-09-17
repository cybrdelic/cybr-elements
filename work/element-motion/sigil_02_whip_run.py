"""Bounded streaming native solver -> mesh -> Cycles, all logs kept on disk."""
from pathlib import Path
import subprocess,sys,time,json,shutil
R=Path(__file__).resolve().parent;full='--full' in sys.argv;O=R/'sigil-02-water-whip'/('full' if full else 'cpu')
if (O/'particles/manifest.json').exists():
 raise SystemExit('This revision already contains a simulation. Use a fresh revision directory; completed caches must not be overwritten.')
blender='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
commands=[['node',str(R/'sigil_02_whip_water.mjs')]+(['--full'] if full else []),[sys.executable,str(R/'sigil_02_whip_mesh.py')]+(['--full'] if full else ['--preview']),[blender,'--background','--python',str(R/'sigil_02_whip_render.py'),'--']+(['--full'] if full else ['--preview'])]
processes=[];logs=[]
try:
 for name,cmd in zip(['sim','mesh','render'],commands):
  log=(O/f'{name}.log').open('w');logs.append(log);p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT);processes.append((name,p))
 (O/'processes.json').write_text(json.dumps({n:p.pid for n,p in processes}))
 while any(p.poll() is None for _,p in processes):
  failures=[(n,p.returncode) for n,p in processes if p.poll() not in [None,0]]
  if failures:raise RuntimeError(str(failures))
  if shutil.disk_usage(O).free<40*2**20:raise RuntimeError('Stopped before disk exhaustion')
  time.sleep(3)
 print('Full water sequence complete.' if full else 'CPU water motion preview complete.',flush=True)
finally:
 for _,p in processes:
  if p.poll() is None:p.terminate()
 for log in logs:log.close()
