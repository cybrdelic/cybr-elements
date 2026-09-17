"""One material job, bounded logs, fail-fast pipeline supervision."""
from pathlib import Path
import sys,time,subprocess,json,os
R=Path(__file__).resolve().parent;B=R/'sigil-v1';PY=sys.executable;BL=r'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe'
element,variant=sys.argv[1:3];extra=sys.argv[3:];stem=f'{element}-{variant}'
jobs=[];handles=[]
def launch(cmd,label):
 h=(B/f'{stem}-{label}.log').open('w',encoding='utf-8');handles.append(h);p=subprocess.Popen(cmd,stdout=h,stderr=subprocess.STDOUT);jobs.append((p,label));print(json.dumps(dict(started=label,pid=p.pid,command=cmd)),flush=True)
try:
 if element=='water':
  launch(['node',str(R/'sigil_water.mjs'),variant],'native')
  launch([PY,str(R/'sigil_mesh.py'),variant],'mesh')
  launch([BL,'-b','--factory-startup','--python-exit-code','1','--python',str(R/'sigil_water_render.py'),'--',variant,*extra],'render')
 elif element=='earth':launch([BL,'-b','--factory-startup','--python-exit-code','1','--python',str(R/'sigil_earth.py'),'--',variant,*extra],'render')
 elif element in ['fire','air']:launch([PY,str(R/'sigil_gas.py'),element,variant,*extra],'render')
 else:raise ValueError(element)
 while True:
  status=[(p.poll(),label) for p,label in jobs]
  for code,label in status:
   if code not in [None,0]:raise RuntimeError(f'{label} failed: {code}')
  if all(code==0 for code,_ in status):break
  time.sleep(1)
 if '--pilot' not in extra:subprocess.run([PY,str(R/'sigil_audit.py'),element,variant],check=True)
 print('COMPLETE '+stem,flush=True)
finally:
 for p,label in jobs:
  if p.poll() is None:p.terminate()
 for h in handles:h.close()
