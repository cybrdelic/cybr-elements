"""Ballistic transport of the unresolved sparse residue after the bulk exit."""
from pathlib import Path
import json,gzip,sys,shutil
import numpy as np
R=Path(__file__).resolve().parent;O=R/'sigil-02-repair';sys.path.insert(0,str(R.parent/'flip-lettering/vendor/tools'))
from mesh_iii import encode
cache=O/'water-ballistic-mesh';frames=O/'water-final-frames';cache.mkdir(exist_ok=True);frames.mkdir(exist_ok=True)
m=json.loads((O/'water-release-particles/manifest.json').read_text());start=175;total=240
for f in range(start+1):shutil.copy2(O/f'water-release-frames/{f:04}.jpg',frames/f'{f:04}.jpg')
n=m['frames'][start]['particles'];a=np.frombuffer(gzip.decompress((O/f'water-release-particles/{start:04}.gz').read_bytes()),'<f4');p=a[:n*3].reshape(-1,3).copy();v=a[n*3:n*6].reshape(-1,3).copy();radius=np.cbrt((m['config']['h']*.5)**3*3/(4*np.pi));r=np.full(n,radius,np.float32)
# Once the bulk is gone these sparse parcels cannot support the grid pressure
# projection. Continue their measured positions/velocities under gravity and
# sphere drag. Source scale and nominal parcel volume are unchanged.
extent=np.array(m['config']['extent']);empty=np.empty((0,3),np.float32);faces=np.empty((0,3),np.uint32);rows=[]
for f in range(start+1,total):
 for _ in range(3):
  dt=m['frameDt']/3;v[:,1]-=9.81*dt;relative=v-np.array([.035,0,.020],np.float32);speed=np.linalg.norm(relative,axis=1)
  drag=3*1.225*.47/(8*1000*np.maximum(r,.00002))*speed;v-=relative*(1-np.exp(-drag*dt))[:,None];p+=v*dt
 keep=p[:,1]>.12;p=p[keep];v=v[keep];r=r[keep]
 assert np.isfinite(p).all() and np.isfinite(v).all()
 np.savez_compressed(cache/f'{f:04}.velocity.npz',surface=empty,drops=v,drop_positions=p)
 encode(cache/f'{f:04}.mesh.gz',empty,empty,faces,p,r,np.empty((0,6),np.float32),p,extent,np.empty(0,np.float32),np.zeros((1,1,2),np.uint8))
 rows.append(dict(frame=f,parcels=len(p),outflowParcels=n-len(p),finite=True))
(cache/'manifest.json').write_text(json.dumps(m));assert len(p)==0
(O/'water-ballistic-tail-report.json').write_text(json.dumps(dict(startFrame=start,frames=total,model='Native residual parcel positions/velocities followed by gravity and quadratic sphere drag after the bulk fluid exits. Off-camera outflow, no image fade.',initialParcels=n,firstEmptyFrame=next(x['frame'] for x in rows if x['parcels']==0),rows=rows),indent=2))
s=(R/'sigil_02_water_release_render.py').read_text().replace('water-release-mesh','water-ballistic-mesh').replace('water-release-frames','water-final-frames').replace('range(216)','range(240)')
(R/'sigil_02_water_sparse_render.py').write_text(s)
print(json.dumps({'tailFrames':total-start-1,'firstEmpty':next(x['frame'] for x in rows if x['parcels']==0),'allFinite':True}))
