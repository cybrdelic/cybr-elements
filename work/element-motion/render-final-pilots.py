from pathlib import Path
import subprocess,time
R=Path(__file__).resolve().parent
while 'READY foam pilot' not in (R/'subelements/optical-final.log').read_text(encoding='utf-8',errors='replace'):time.sleep(5)
bl='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
for kind in ['mud','blood','healing','spirit','metal','plants']:
 script='photo-geometry.py' if kind in ['metal','plants'] else 'photo-foam.py'
 with (R/'subelements'/f'pilot-final-{kind}.log').open('w',encoding='utf-8') as log:subprocess.run([bl,'-b','-t','3','--python',str(R/script),'--','--kind',kind],stdout=log,stderr=subprocess.STDOUT,check=True)
 print('FINISHED',kind,flush=True)
