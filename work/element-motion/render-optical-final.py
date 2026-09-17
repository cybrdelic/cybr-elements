from pathlib import Path
import subprocess,time
R=Path(__file__).resolve().parent
while 'FINISHED combustion' not in (R/'subelements/photo-followon.log').read_text(encoding='utf-8',errors='replace'):time.sleep(5)
bl='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
for kind in ['ice','glass']:
 with (R/'subelements'/f'optical-final-{kind}.log').open('w',encoding='utf-8') as log:subprocess.run([bl,'-b','-t','3','--python',str(R/'photo-solids.py'),'--','--kind',kind,'--full'],stdout=log,stderr=subprocess.STDOUT,check=True)
 subprocess.run(['python',str(R/'encode-subelement.py'),'photo-'+kind],check=True);print('FINISHED',kind,flush=True)
with (R/'subelements/foam-pilot2.log').open('w',encoding='utf-8') as log:subprocess.run([bl,'-b','-t','3','--python',str(R/'photo-foam.py'),'--','--kind','foam'],stdout=log,stderr=subprocess.STDOUT,check=True)
print('READY foam pilot',flush=True)
