"""Keep completed images; correct off-camera culling and overlap only safe work."""
from pathlib import Path
import subprocess,sys,time,json,psutil,shutil
from PIL import Image
R=Path(__file__).resolve().parent;O=R/'sigil-02-repair';ROOT=R.parents[1];PY=sys.executable;BLENDER=r'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe'
for proc in psutil.process_iter():
 try:
  args=proc.cmdline()
  if any(a.endswith('sigil_02_repair_resume.py') for a in args) and proc.pid!=psutil.Process().pid:proc.terminate()
 except (psutil.NoSuchProcess,psutil.AccessDenied):pass
for pid in json.loads((O/'full-jobs.json').read_text()).values():
 try:
  proc=psutil.Process(pid)
  if any('sigil_02_repair_' in a for a in proc.cmdline()):proc.terminate()
 except psutil.NoSuchProcess:pass
time.sleep(2)
for image in (O/'water-frames').glob('*.jpg'):
 with Image.open(image) as im:im.verify()
for name in ['water-particles','water-mesh']:
 folder=O/name;assert folder.resolve().parent==O.resolve()
 for file in folder.iterdir():
  if file.is_file() and (file.suffix!='.json' or file.name=='manifest.json'):file.unlink()
# The camera is wider than the original pilot. World z=-2.46 is safely below
# its lower edge, whereas the inherited -.48-solver cutoff was visible.
p=R/'sigil_02_repair_water_mesh_resume.py';s=p.read_text();assert 'p[:,1]>.48' in s;s=s.replace('p[:,1]>.48','p[:,1]>.12');p.write_text(s)
(O/'continue-water').write_text('Late-frame review complete; off-camera reconstruction bounds corrected.')
children=[];logs=[]
def start(name,args):
 a=(O/f'{name}.log').open('w');b=(O/f'{name}.err').open('w');logs.extend([a,b]);p=subprocess.Popen(args,cwd=ROOT,stdout=a,stderr=b,creationflags=subprocess.CREATE_NO_WINDOW);children.append((name,p));(O/'full-jobs.json').write_text(json.dumps({n:p.pid for n,p in children},indent=2));return p
def check():
 for n,p in children:
  if p.poll() not in [0,None]:raise RuntimeError(f'{n} failed: {p.returncode}')
 if shutil.disk_usage(ROOT).free<350*1024**2:raise RuntimeError('Disk headroom below safety threshold')
try:
 start('water-sim-full',['node',str(R/'sigil_02_repair_water.mjs'),'--ungated'])
 start('water-mesh-full',[PY,str(R/'sigil_02_repair_water_mesh_resume.py')])
 # Earth renders while the CPU rebuilds water's history. Only one GPU render
 # process is active; this saves a separate idle replay period.
 earth=start('earth-full',[BLENDER,'--background','--factory-startup','--python-exit-code','1','--python',str(R/'sigil_02_repair_earth_scanned.py'),'--','--full'])
 while earth.poll() is None:check();time.sleep(2)
 check();print('EARTH COMPLETE',flush=True)
 water=start('water-render-full',[BLENDER,'--background','--factory-startup','--python-exit-code','1','--python',str(R/'sigil_02_repair_water_render.py'),'--','--full'])
 while any(p.poll() is None for n,p in children):check();time.sleep(2)
 check();print('WATER COMPLETE',flush=True)
 lightning=start('lightning-full',[PY,str(R/'sigil_02_repair_lightning_ensemble.py'),'--full'])
 while lightning.poll() is None:check();time.sleep(2)
 check();print('ALL THREE SEQUENCES COMPLETE',flush=True)
except BaseException:
 for n,p in children:
  if p.poll() is None:p.terminate()
 raise
finally:
 for h in logs:h.close()
