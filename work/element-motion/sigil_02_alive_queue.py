"""One GPU render at a time; stop before publication for visual review."""
from pathlib import Path
import subprocess,time,sys,json,psutil
R=Path(__file__).resolve().parent;O=R/'sigil-02-alive';W=R/'sigil-02-water-arrival/full';blender=r'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe'
deadline=time.monotonic()+900
while not (O/'earth-report.json').exists():
 if time.monotonic()>deadline:raise TimeoutError('Earth renderer did not finish')
 time.sleep(.5)
for p in psutil.process_iter(['name','cmdline'],ad_value=None):
 try:
  if (p.info['name'] or '').lower()=='blender.exe' and any('sigil_02_alive_earth_render.py' in a for a in p.info['cmdline'] or []):p.wait(timeout=60)
 except psutil.NoSuchProcess:pass
assert all(r['finite'] for r in json.loads((O/'earth-report.json').read_text())['rows'])
with (W/'render-alive-resume.log').open('w') as log:
 subprocess.run([blender,'-b','-t','3','--python',str(R/'sigil_02_water_arrival_full_render.py'),'--','--full'],stdout=log,stderr=subprocess.STDOUT,check=True)
with (O/'encode-audit.log').open('w') as log:
 for script,args in [('sigil_02_water_arrival_finish.py',['encode']),('sigil_02_alive_finish.py',['encode','earth'])]:
  if args==['encode','earth'] and (O/'earth-audit.json').exists():continue
  subprocess.run([sys.executable,str(R/script),*args],stdout=log,stderr=subprocess.STDOUT,check=True)
print('Water and earth encoded and decoded; visual publication review still required.',flush=True)
