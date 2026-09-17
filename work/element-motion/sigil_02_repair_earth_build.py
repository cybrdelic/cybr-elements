"""Adapt the original Bullet stream, without per-clast target springs."""
from pathlib import Path
import numpy as np,json
from scipy.ndimage import map_coordinates
R=Path(__file__).resolve().parent;O=R/'sigil-02-repair';src=np.load(R/'sigil-02-v2/source.npz');lo=src['lo'];ext=src['extent'];shape=src['sdf'].shape
def sample(name,x,z):
 return float(map_coordinates(src[name],[[(z-lo[2])/ext[2]*(shape[0]-1)],[(x-lo[0])/ext[0]*(shape[1]-1)]],order=1,mode='constant',cval=-1 if name=='sdf' else 0)[0])
rng=np.random.default_rng(30915);rows=[]
for attempt in range(16000):
 k=len(rows);x=rng.uniform(-4,4);z=rng.uniform(.60,3.32);sd=sample('sdf',x,z)
 if sd<.012:continue
 r=rng.uniform(.17,.31) if attempt<2000 else rng.uniform(.068,.135) if attempt<7500 else rng.uniform(.022,.052)
 if sd<r*.24:continue
 center=np.array([x,rng.uniform(-.42,.42)+.22*np.sin(x*1.25),z]);t=.23+(sample('arrival',x,z)-.3)/3.6*1.85
 d=np.array([sample('dirx',x,z),0,sample('dirz',x,z)]);d/=max(.01,np.linalg.norm(d))
 vel=d*(.48+.2*rng.random())+np.array([0,.36*np.cos(x*1.7+z*2),.16])
 clear=True
 for row in rows:
  age=t-row['time']
  pred=np.array(row['center'])+np.array(row['velocity'])*age+np.array([0,0,-.11*age*age]) if age>=0 else np.array(row['center'])
  if np.linalg.norm(center-pred)<r+row['radius']+.008:clear=False;break
 if not clear:continue
 rows.append(dict(time=t,center=center.tolist(),velocity=vel.tolist(),radius=r))
 if len(rows)>=540:break
rows.sort(key=lambda q:q['time']);(O/'earth-source.json').write_text(json.dumps(rows));print('Earth source bodies',len(rows),'hero clasts',sum(r['radius']>.16 for r in rows))
s=(R/'bending-earth-v5.py').read_text()
s=s.replace("out=R/'bending-rebuild-v5/earth-frames'","out=R/('sigil-02-repair/earth-frames' if '--full' in sys.argv else 'sigil-02-repair/earth-pilot')")
s=s.replace("s.cycles.device='GPU'","s.cycles.device='GPU' if '--full' in sys.argv else 'CPU'").replace('s.cycles.samples=64',"s.cycles.samples=72 if '--full' in sys.argv else 24")
s=s.replace('s.render.resolution_x=1920;s.render.resolution_y=1080',"s.render.resolution_x=1920 if '--full' in sys.argv else 1280;s.render.resolution_y=1080 if '--full' in sys.argv else 720")
s=s.replace('s.frame_end=120','s.frame_end=192').replace('frame_end=120','frame_end=192')
s=s.replace("s.gravity=(0,0,-.5);s.keyframe_insert('gravity',frame=1);s.keyframe_insert('gravity',frame=51);s.gravity=(0,0,-9.81);s.keyframe_insert('gravity',frame=65)","s.gravity=(0,0,-.22);s.keyframe_insert('gravity',frame=1);s.keyframe_insert('gravity',frame=106);s.gravity=(0,0,-9.81);s.keyframe_insert('gravity',frame=125)")
s=s.replace('floor.location.z=-3','floor.location.z=-5')
begin=s.index('for k in range(660):');end=s.index(" src=data['pieces']",begin)
s=s[:begin]+'''source_rows=json.loads((R/'sigil-02-repair/earth-source.json').read_text())
for k,row in enumerate(source_rows):
 b=2+int(row['time']*30);t=(b-1)/30;center=Vector(row['center']);vel=Vector(row['velocity']);r=row['radius'];p=np.array([center.x,center.z])
'''+s[end:]
s=s.replace("rockMats=[material('Slate interior',(.055,.038,.022)),material('Fresh fracture',(.085,.064,.038)),material('Weathered seams',(.018,.012,.007)),material('Mineral inclusion',(.10,.085,.057))]","rockMats=[material('Basalt interior',(.048,.042,.033)),material('Fresh fracture',(.090,.082,.064)),material('Weathered seams',(.010,.009,.007)),material('Mineral inclusion',(.14,.12,.083))]")
s=s.replace("cam.data.type='ORTHO';cam.data.ortho_scale=DATA['camera']['width'];s.camera=cam","cam.location=(.65,-13.,3.05);cam.rotation_euler=(Vector((0,0,1.8))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='PERSP';cam.data.lens=44;s.camera=cam")
s=s.replace('range(1,121)','range(1,193)').replace("f in [21,51,81]","f in [46,67,91,145]")
begin=s.index(' if f==51 and not full:');end=s.index(' if f%15==0:',begin);s=s[:begin]+s[end:]
s=s.replace("R/'bending-rebuild-v5/earth-transforms.npz'","R/'sigil-02-repair/earth-transforms.npz'").replace("R/'bending-rebuild-v5/earth-report.json'","R/'sigil-02-repair/earth-report.json'")
s=s.replace("'frames':120","'frames':192").replace("'trail':'shared-trail.json'","'trail':'Full02 variable-width 3D source'").replace("'lift':'Effective gravity .5 m/s2 during drawing, ramp to 9.81 after frame 51; Bullet free release and contacts'","'lift':'Effective gravity .22 during bending, 9.81 on release after frame106. Bullet convex-hull contacts; no target springs.'")
s=s.replace('gp[active,2]','gp[active,2]')
s=s.replace('(gp[:,2]<gr-3)','(gp[:,2]<gr-5)').replace('gp[hit,2]=gr[hit]-3','gp[hit,2]=gr[hit]-5')
s=s.replace('s.rigidbody_world.substeps_per_frame=16','s.rigidbody_world.substeps_per_frame=20')
# Camera-shutter blur now comes from actual rigid-body movement.
s=s.replace("full='--full' in sys.argv;start=time.time();transforms=[]","s.render.use_motion_blur=True;s.render.motion_blur_shutter=.4\nfull='--full' in sys.argv;start=time.time();transforms=[]")
(R/'sigil_02_repair_earth.py').write_text(s)
