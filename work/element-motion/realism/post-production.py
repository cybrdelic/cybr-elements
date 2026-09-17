from pathlib import Path
import subprocess,sys,time,json
R=Path(__file__).resolve().parent;checks={'production-a2':4,'production-b':3,'production-c':11,'production-d':1};started=time.time()
print('Waiting for the complete black-background render groups.',flush=True)
while True:
 ready=True
 for name,count in checks.items():
  p=R/(name+'-status.json')
  try:rows=json.loads(p.read_text(encoding='utf-8'))
  except (FileNotFoundError,json.JSONDecodeError):rows=[]
  if len(rows)!=count or not all(row['ok'] for row in rows):ready=False
  if p.exists() and p.stat().st_mtime>started and any(not row['ok'] for row in rows):raise RuntimeError('Render failed: '+name)
 if ready:break
 time.sleep(5)
print('All Blender groups completed. Rendering the corrected combustion volume.',flush=True)
with (R/'combustion-final.log').open('w',encoding='utf-8') as log:
 result=subprocess.run([sys.executable,str(R/'combustion.py'),'--name','rebuilt-combustion-final','--size','480','128','224','--seconds','4','--warmup','0','--fps','30','--substeps','8'],stdout=log,stderr=subprocess.STDOUT)
if result.returncode:
 print((R/'combustion-final.log').read_bytes()[-1200:].decode('utf-8',errors='replace').encode('ascii','replace').decode());raise RuntimeError('Combustion render failed')
print('Combustion completed. Validating and encoding all 23 studies.',flush=True)
kinds=['lava','metal','foam','ice','glass','crystal','mud','blood','plants','sand','snow','combustion','lightning','lightning-redirection','healing','spirit','energy','spirit-projection','seismic','sound','flight','pressure','heat']
subprocess.run([sys.executable,str(R/'encode.py'),*kinds],check=True)
(R/'ready-for-final-review.json').write_text(json.dumps({'count':len(kinds),'elapsed':time.time()-started,'kinds':kinds}),encoding='utf-8');print('All 23 encoded; ready for final visual and browser review.',flush=True)
