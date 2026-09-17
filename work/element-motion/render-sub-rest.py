from pathlib import Path
import subprocess,sys,time
R=Path(__file__).resolve().parent;blender='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
while 'BATCH COMPLETE' not in (R/'subelements/batch.log').read_text(encoding='utf-8',errors='replace'):time.sleep(2)
for kind in ['ice','glass','crystal','sand','snow']:
 script=R/('sub-solid.py' if kind in ['ice','glass','crystal'] else f'sub-{kind}.py')
 with (R/'subelements'/f'{kind}-full.log').open('w',encoding='utf-8') as log:subprocess.run([blender,'-b','--python',str(script),'--','--kind',kind,'--full'],stdout=log,stderr=subprocess.STDOUT,check=True)
 subprocess.run([sys.executable,str(R/'encode-subelement.py'),kind],check=True)
for script in ['sub-gas.py','sub-blue-fire.py','sub-combustion.py']:
 with (R/'subelements'/(script+'.log')).open('w',encoding='utf-8') as log:subprocess.run([sys.executable,str(R/script),'--size','480','96','288','--fps','30','--substeps','6'],stdout=log,stderr=subprocess.STDOUT,check=True)
 print('VOLUME',script,'complete',flush=True)
print('REST COMPLETE',flush=True)
