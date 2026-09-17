from pathlib import Path
import subprocess,sys,time,json,shutil
R=Path(__file__).resolve().parent;O=R/'sigil-02-repair';ROOT=R.parents[1]
jobs={};logs=[]
try:
 for name,args in [
  ('outflow-sim',['node',str(R/'sigil_02_water_outflow.mjs'),'--ungated']),
  ('outflow-mesh',[sys.executable,str(R/'sigil_02_water_outflow_mesh.py')]),
  ('outflow-render',[r'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe','--background','--factory-startup','--python-exit-code','1','--python',str(R/'sigil_02_water_outflow_render.py'),'--','--full'])]:
  a=(O/f'{name}.log').open('w');b=(O/f'{name}.err').open('w');logs.extend([a,b]);jobs[name]=subprocess.Popen(args,cwd=ROOT,stdout=a,stderr=b,creationflags=subprocess.CREATE_NO_WINDOW)
 (O/'outflow-jobs.json').write_text(json.dumps({n:p.pid for n,p in jobs.items()}))
 while any(p.poll() is None for p in jobs.values()):
  for n,p in jobs.items():
   if p.poll() not in [None,0]:raise RuntimeError(f'{n}: {p.returncode}')
  if shutil.disk_usage(ROOT).free<350*1024**2:raise RuntimeError('Disk headroom')
  time.sleep(2)
 print('OUTFLOW COMPLETE',flush=True)
finally:
 for p in jobs.values():
  if p.poll() is None:p.terminate()
 for f in logs:f.close()
