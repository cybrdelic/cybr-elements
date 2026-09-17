"""CPU preparation of full-width liquid and discrete stone source volumes."""
from pathlib import Path
import json
import numpy as np
from scipy.ndimage import map_coordinates
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent;O=R/'sigil-02-elements';O.mkdir(exist_ok=True)
src=np.load(R/'sigil-02-v2/source.npz');lo=src['lo'];ext=src['extent'];shape=src['sdf'].shape
def sample(name,x,z):
 return map_coordinates(src[name],[(z-lo[2])/ext[2]*(shape[0]-1),(x-lo[0])/ext[0]*(shape[1]-1)],order=1,mode='constant',cval=-1 if name=='sdf' else 0)
rng=np.random.default_rng(20971)
# Rounded liquid strokes with a real depth cross-section; no walls or fitted mesh.
h=.018;scale=.35;origin=np.array([2.1,.98,.63]);spacing=h*.5/scale
x,z=np.meshgrid(np.arange(-4.02,4.03,spacing),np.arange(.60,3.31,spacing))
x=x.ravel();z=z.ravel();d=sample('sdf',x,z);valid=d>0;x=x[valid];z=z[valid];d=d[valid]
points=[];birth=[];vel=[]
for y in np.arange(-.46,.47,spacing):
 center=.11*np.sin(x*2.9+z*4.1)+.055*np.sin(x*7-z*5)
 depth=np.minimum(.23,np.sqrt(np.maximum(d,0)*.32))
 q=np.abs(y-center)<depth
 if not q.any():continue
 a=x[q];b=z[q];dy=np.full(len(a),y)
 p=np.column_stack((a,b,dy))+rng.uniform(-spacing*.2,spacing*.2,(len(a),3))
 t=sample('arrival',a,b)
 tx=sample('dirx',a,b);tz=sample('dirz',a,b)
 # Source momentum enters the native pressure solve. It is never imposed again.
 v=np.column_stack((tx*.085+.016*np.sin(b*13),tz*.085,.042*np.sin(a*8+b*7)))
 points.append(p*scale+origin);birth.append(t);vel.append(v)
points=np.concatenate(points);birth=np.concatenate(birth);vel=np.concatenate(vel)
order=np.argsort(birth);water=np.column_stack((birth[order],points[order],vel[order])).astype('<f4');water.tofile(O/'water-source.f32')
# Non-overlapping broad distribution of original uncut stone meshes.
centers=[];radii=[];times=[];dirs=[]
for attempt in range(36000):
 x=rng.uniform(-4,4);z=rng.uniform(.65,3.25);sd=float(sample('sdf',np.array([x]),np.array([z]))[0])
 if sd<.008:continue
 radius=min(.16,.019/max(.028,rng.random())**.62)
 radius=min(radius,max(.015,sd*.8))
 depth=min(.19,np.sqrt(sd*.19));y=rng.uniform(-depth,depth)+.045*np.sin(x*4+z*3)
 c=np.array([x,y,z])
 if centers and np.any(np.linalg.norm(np.asarray(centers)-c,axis=1)<np.asarray(radii)+radius+.002):continue
 centers.append(c);radii.append(radius);times.append(float(sample('arrival',np.array([x]),np.array([z]))[0]));dirs.append([float(sample('dirx',np.array([x]),np.array([z]))[0]),0,float(sample('dirz',np.array([x]),np.array([z]))[0])])
 if len(centers)>=2400:break
np.savez_compressed(O/'earth-source.npz',centers=centers,radii=radii,births=times,directions=dirs)
report={'waterParticles':len(water),'liquidPhysicalVolume':len(water)*(h*.5)**3,'waterSpacingWorld':spacing,'waterMaxDepthWorld':.46,'waterScale':scale,'waterOrigin':origin.tolist(),'earthBodies':len(centers),'earthRadiusRange':[min(radii),max(radii)],'source':'Complete approved 02 silhouette with rounded depth and material-specific emission; no skeleton width substitution'}
(O/'material-source-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
