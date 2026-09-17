from pathlib import Path
import subprocess
R=Path(__file__).resolve().parent
for kind in ['healing','spirit']:
 print('START',kind,flush=True)
 with (R/'subelements'/f'finish-{kind}.log').open('w',encoding='utf-8') as log:
  subprocess.run(['C:/Program Files/Blender Foundation/Blender 4.5/blender.exe','-b','-t','3','--python',str(R/'sub-fields.py'),'--','--kind',kind,'--full'],stdout=log,stderr=subprocess.STDOUT,check=True)
 assert 'Traceback (most recent call last)' not in (R/'subelements'/f'finish-{kind}.log').read_text(encoding='utf-8',errors='replace')
 subprocess.run(['python',str(R/'encode-subelement.py'),'field-'+kind],check=True)
 print('FINISHED',kind,flush=True)
