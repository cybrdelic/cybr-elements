from pathlib import Path
import subprocess,time,psutil,sys
R=Path(__file__).resolve().parent;O=R/'sigil-02-elements';blender=r'C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
def water_running():
 for p in psutil.process_iter(['name','cmdline']):
  try:
   if p.info['name'].lower()=='blender.exe' and any(str(q).endswith('sigil_02_water_render.py') for q in p.info['cmdline'] or []):return True
  except psutil.Error:pass
 return False
while water_running():time.sleep(2)
assert len(list((O/'water-frames').glob('*.jpg')))==294,'Water incomplete; do not race or hide failure'
with (O/'earth-render-v3.log').open('w') as log:subprocess.run([blender,'--background','--factory-startup','--python-exit-code','1','--python',str(R/'sigil_02_earth_render_v3.py')],stdout=log,stderr=subprocess.STDOUT,check=True)
with (O/'air-run-v2.log').open('w') as log:subprocess.run([sys.executable,str(R/'sigil_02_air_v2.py'),'--size','896','56','504','--fps','30','--substeps','4'],stdout=log,stderr=subprocess.STDOUT,check=True)
print('Sequential GPU queue complete',flush=True)
