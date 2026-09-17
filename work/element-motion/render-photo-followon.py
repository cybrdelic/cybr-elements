from pathlib import Path
import subprocess,time
R=Path(__file__).resolve().parent
while 'FINISHED lightning' not in (R/'subelements/photo-batch.log').read_text(encoding='utf-8',errors='replace'):time.sleep(5)
bl='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
jobs=[('crystal-refine',[bl,'-b','-t','3','--python',str(R/'photo-solids.py'),'--','--kind','crystal','--full']),('crystal-encode',['python',str(R/'encode-subelement.py'),'photo-crystal']),('foam-pilot',[bl,'-b','-t','3','--python',str(R/'photo-foam.py'),'--','--kind','foam']),('sand-pilot',[bl,'-b','-t','3','--python',str(R/'sub-sand.py')]),('snow-pilot',[bl,'-b','-t','3','--python',str(R/'sub-snow.py')]),('gas',['python',str(R/'sub-gas.py'),'--size','480','96','288','--fps','30','--substeps','6']),('blue-fire',['python',str(R/'sub-blue-fire.py'),'--size','480','96','288','--fps','30','--substeps','6']),('combustion',['python',str(R/'sub-combustion.py'),'--size','480','96','288','--fps','30','--substeps','6'])]
for kind,cmd in jobs:
 print('START',kind,flush=True)
 with (R/'subelements'/f'rebuild-{kind}.log').open('w',encoding='utf-8') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
 print('FINISHED',kind,flush=True)
