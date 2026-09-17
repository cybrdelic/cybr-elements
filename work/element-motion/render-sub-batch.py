from pathlib import Path
import subprocess,sys
R=Path(__file__).resolve().parent;blender='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
for kind in ['lava','foam','mud','blood','healing','spirit','metal','plants']:
 script=R/('sub-geometry.py' if kind in ['metal','plants'] else 'sub-fluid.py')
 # Always replace pilot frames with the final configuration.
 with (R/'subelements'/f'{kind}-full.log').open('w',encoding='utf-8') as log:subprocess.run([blender,'-b','--python',str(script),'--','--kind',kind,'--full'],stdout=log,stderr=subprocess.STDOUT,check=True)
 subprocess.run([sys.executable,str(R/'encode-subelement.py'),kind],check=True)
print('BATCH COMPLETE',flush=True)
