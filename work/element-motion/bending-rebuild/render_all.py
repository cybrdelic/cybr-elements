"""Sequential GPU queue; retained compressed frames permit interrupted mesh renders to resume."""
from pathlib import Path
import subprocess,sys,json,time
R=Path(__file__).resolve().parent
SOURCE=R.parent
BLENDER=r'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe'
jobs=[
 ('fire',[sys.executable,str(SOURCE/'bending-fire.py'),'--size','576','112','336','--fps','30','--substeps','6']),
 ('air',[sys.executable,str(SOURCE/'bending-air.py'),'--size','576','112','336','--fps','30','--substeps','6']),
 ('earth',[BLENDER,'-b','--factory-startup','--python',str(SOURCE/'bending-earth.py'),'--','--full']),
 ('water',[BLENDER,'-b','--factory-startup','--python',str(SOURCE/'bending-water.py'),'--','--full']),
]
records=[]
for name,command in jobs:
    start=time.time()
    state={'current':name,'started':start,'completed':records}
    (R/'queue-status.json').write_text(json.dumps(state,indent=2))
    print('START',name,flush=True)
    with (R/f'{name}-full.log').open('w',encoding='utf-8') as log:
        proc=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
    records.append({'element':name,'exitCode':proc.returncode,'seconds':round(time.time()-start,1)})
    if proc.returncode:
        (R/'queue-status.json').write_text(json.dumps({'failed':name,'completed':records},indent=2))
        raise RuntimeError(f'{name} failed; see {name}-full.log')
    if name in ['earth','water']:
        subprocess.run([sys.executable,str(R/'encode.py'),name],check=True)
    print('DONE',name,records[-1]['seconds'],flush=True)
(R/'queue-status.json').write_text(json.dumps({'complete':True,'completed':records},indent=2))
print('GPU QUEUE COMPLETE',flush=True)
