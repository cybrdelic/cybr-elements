from pathlib import Path
import subprocess
R=Path(__file__).resolve().parent
bl='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
for kind in ['ice','glass','crystal','lava','lightning']:
 script='photo-solids.py' if kind in ['ice','glass','crystal'] else 'photo-'+kind+'.py'
 with (R/'subelements'/f'photo-{kind}-full.log').open('w',encoding='utf-8') as log:subprocess.run([bl,'-b','-t','3','--python',str(R/script),'--','--kind',kind,'--full'],stdout=log,stderr=subprocess.STDOUT,check=True)
 subprocess.run(['python',str(R/'encode-subelement.py'),'photo-'+kind],check=True)
 print('FINISHED',kind,flush=True)
