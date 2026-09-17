from pathlib import Path
import subprocess
R=Path(__file__).resolve().parent
bl='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
jobs=[('spirit','sub-fields.py','field-spirit'),('energy','sub-fields.py','field-energy'),('blood','photo-foam.py','photo-blood'),('metal','photo-geometry.py','photo-metal'),('plants','photo-geometry.py','photo-plants'),('sand','sub-sand.py','sand'),('snow','sub-snow.py','snow'),('lightning-redirection','photo-lightning-redirection.py','photo-lightning-redirection')]
for kind,script,out in jobs:
 print('START',kind,flush=True)
 with (R/'subelements'/f'finish-{kind}.log').open('w',encoding='utf-8') as log:
  subprocess.run([bl,'-b','-t','3','--python',str(R/script),'--','--kind',kind,'--full','--resume'],stdout=log,stderr=subprocess.STDOUT,check=True)
 text=(R/'subelements'/f'finish-{kind}.log').read_text(encoding='utf-8',errors='replace')
 if 'Traceback (most recent call last)' in text:raise RuntimeError(kind+' failed')
 subprocess.run(['python',str(R/'encode-subelement.py'),out],check=True)
 print('FINISHED',kind,flush=True)
