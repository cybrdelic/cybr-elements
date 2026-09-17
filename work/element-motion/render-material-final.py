from pathlib import Path
import subprocess,time
R=Path(__file__).resolve().parent
while 'FINISHED combustion' not in (R/'subelements/photo-followon.log').read_text(encoding='utf-8',errors='replace'):time.sleep(5)
bl='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
for kind in ['foam','mud','blood','healing','spirit','metal','plants','sand','snow','lightning-redirection']:
 if kind in ['ice','glass']:script='photo-solids.py';out='photo-'+kind
 elif kind in ['foam','mud','blood','healing','spirit']:script='photo-foam.py';out='photo-'+kind
 elif kind in ['metal','plants']:script='photo-geometry.py';out='photo-'+kind
 elif kind in ['sand','snow']:script='sub-'+kind+'.py';out=kind
 else:script='photo-lightning-redirection.py';out='photo-'+kind
 print('START',kind,flush=True)
 with (R/'subelements'/f'finish-{kind}.log').open('w',encoding='utf-8') as log:subprocess.run([bl,'-b','-t','3','--python',str(R/script),'--','--kind',kind,'--full'],stdout=log,stderr=subprocess.STDOUT,check=True)
 subprocess.run(['python',str(R/'encode-subelement.py'),out],check=True)
 print('FINISHED',kind,flush=True)

print('START gas-refine',flush=True)
with (R/'subelements/gas-refine.log').open('w',encoding='utf-8') as log:subprocess.run(['python',str(R/'sub-gas-refine.py'),'--size','480','96','288','--fps','30','--substeps','6'],stdout=log,stderr=subprocess.STDOUT,check=True)
print('FINISHED gas-refine',flush=True)
