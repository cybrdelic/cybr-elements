"""Bounded streaming render queue. One GPU renderer at a time."""
from pathlib import Path
import sys,subprocess,json,time,shutil,psutil
R=Path(__file__).resolve().parent;O=R/'sigil-02-repair';PY=sys.executable;BLENDER=r'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe';ROOT=R.parents[1]
# Stop only the isolated, gated pilot workers owned by this repair run.
jobs=json.loads((O/'water-jobs.json').read_text())
for pid in jobs.values():
 try:
  p=psutil.Process(pid)
  if any('sigil_02_repair_water' in a for a in p.cmdline()):p.terminate()
 except psutil.NoSuchProcess:pass
time.sleep(2)
for name in ['water-particles','water-mesh','water-cpu']:
 folder=O/name
 if folder.exists():
  assert folder.resolve().parent==O.resolve()
  for f in folder.iterdir():
   if f.is_file():f.unlink()
(O/'water-continue').write_text('Motion pilot selected; full sequence remains under review.')
# Retain resolved drops; represent unresolved solitary markers with a
# mass-conserving broad subgrid population rather than one identical marble.
s=(R/'bending_spray_v5.py').read_text().replace('chosen=(~dense)&(energetic[ids]|self.active[ids])','chosen=(~dense)')
s=s.replace('(4+20*weber[new]/(weber[new]+8))','(12+12*weber[new]/(weber[new]+8))')
s=s.replace('radii=np.exp(normal*.65)*(k<fragmentCount[:,None])','radii=np.minimum(6.,(1-uniform(7))**(-1/1.7))*(k<fragmentCount[:,None])')
s=s.replace("'Energy-gated, persistent 4..24 volume-normalized fragments; local relative-velocity Weber and support-loss criteria; coherent isolated markers remain drops; bounded added dispersion energy'","'Unresolved solitary parcels use persistent 12..24 truncated-Pareto fragments; dense clusters remain coherent drops. Exact parcel volume, source momentum and bounded extra dispersion are retained.'")
(R/'sigil_02_repair_spray.py').write_text(s)
p=R/'sigil_02_repair_water_mesh.py';s=p.read_text().replace('from bending_spray_v5 import Spray','from sigil_02_repair_spray import Spray')
# Tiny late camera-visible remnants cannot support an isosurface.
s=s.replace(' if n>4:\n  origin=', ' if n>2048:\n  origin=')
s=s.replace("verts=normals=drops=vv=dv=np.empty((0,3),np.float32);faces=np.empty((0,3),np.uint32);radii=np.empty(0,np.float32);measure={}","verts=normals=vv=np.empty((0,3),np.float32);faces=np.empty((0,3),np.uint32);drops=p.copy();dv=v.copy();radii=np.full(n,np.cbrt((h*.5)**3*3/(4*np.pi)),np.float32);measure={'sparseTail':True}")
p.write_text(s)
children=[];handles=[]
def start(name,args):
 log=(O/f'{name}.log').open('w');err=(O/f'{name}.err').open('w');handles.extend([log,err]);p=subprocess.Popen(args,cwd=ROOT,stdout=log,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW);children.append((name,p));return p
start('lightning-full',[PY,str(R/'sigil_02_repair_lightning_branched.py'),'--full'])
water=[start('water-sim-full',['node',str(R/'sigil_02_repair_water.mjs'),'--ungated']),start('water-mesh-full',[PY,str(R/'sigil_02_repair_water_mesh.py')]),start('water-render-full',[BLENDER,'--background','--factory-startup','--python-exit-code','1','--python',str(R/'sigil_02_repair_water_render.py'),'--','--full'])]
(O/'full-jobs.json').write_text(json.dumps({n:p.pid for n,p in children},indent=2))
started=time.time()
try:
 while any(p.poll() is None for p in water):
  for n,p in children:
   if p.poll() not in [None,0]:raise RuntimeError(f'{n} exited {p.returncode}; see {n}.err')
  if shutil.disk_usage(ROOT).free<350*1024**2:raise RuntimeError('Insufficient disk headroom')
  time.sleep(2)
 print('WATER full sequence rendered',round(time.time()-started),flush=True)
 e=start('earth-full',[BLENDER,'--background','--factory-startup','--python-exit-code','1','--python',str(R/'sigil_02_repair_earth_detail.py'),'--','--full'])
 (O/'full-jobs.json').write_text(json.dumps({n:p.pid for n,p in children},indent=2))
 while any(p.poll() is None for n,p in children):
  for n,p in children:
   if p.poll() not in [None,0]:raise RuntimeError(f'{n} exited {p.returncode}; see {n}.err')
  time.sleep(2)
 print('ALL CANDIDATE SEQUENCES READY',round(time.time()-started),flush=True)
except BaseException:
 for n,p in children:
  if p.poll() is None:p.terminate()
 raise
finally:
 for h in handles:h.close()
