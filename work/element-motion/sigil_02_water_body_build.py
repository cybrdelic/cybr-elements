"""Full approved 02 volume: rounded 3D liquid cross sections, guided pressure solve."""
from pathlib import Path
import json,numpy as np
from scipy.ndimage import map_coordinates,distance_transform_edt,gaussian_filter
from skimage.morphology import medial_axis
R=Path(__file__).resolve().parent;O=R/'sigil-02-water-hold';out=O/'body-correction';out.mkdir(exist_ok=True)
c=json.loads((O/'config.json').read_text());src=dict(np.load(R/'sigil-02-v2/source.npz'));lo=src['lo'];ext=src['extent'];shape=src['sdf'].shape
skel,dist=medial_axis(src['sdf']>0,return_distance=True,rng=1871)
nearest=distance_transform_edt(~skel,return_distances=False,return_indices=True)
src['local_radius']=np.maximum(.025,dist[tuple(nearest)]*ext[0]/(shape[1]-1))
def sample(name,x,z):
 return map_coordinates(src[name],[(z-lo[2])/ext[2]*(shape[0]-1),(x-lo[0])/ext[0]*(shape[1]-1)],order=1,mode='constant',cval=-2 if name=='sdf' else 0)
def properties(x,z):
 d=sample('sdf',x,z);r=sample('local_radius',x,z)
 depth=np.sqrt(np.maximum(0,d*(2*r-d)))*1.1
 center=.20*np.sin(x*1.25)+.055*np.sin(x*2.1+z*1.7)
 return d,depth,center
spacing=.009/c['spaceScale'];rng=np.random.default_rng(6415)
x,z=np.meshgrid(np.arange(-4.08,4.09,spacing),np.arange(.42,3.5,spacing));x=x.ravel();z=z.ravel();d,depth,center=properties(x,z);keep=d>0;x=x[keep];z=z[keep];depth=depth[keep];center=center[keep]
rows=[]
for y in np.arange(-.38,.381,spacing):
 keep=abs(y)<depth;a=x[keep];b=z[keep];cy=center[keep]
 if not len(a):continue
 p=np.column_stack((a,b,cy+y));p+=rng.uniform(-spacing*.12,spacing*.12,p.shape)
 tx=sample('dirx',a,b);tz=sample('dirz',a,b);norm=np.maximum(.01,np.hypot(tx,tz));tx/=norm;tz/=norm
 speed=.065*(1+.18*np.sin(a*5+b*3));v=np.column_stack((tx*speed-tz*y*.16,tz*speed+tx*y*.16,.20*np.cos(a*1.25)*tx*speed))
 birth=.25+(sample('arrival',a,b)-.30)/3.60*1.75
 rows.append(np.column_stack((birth,p*c['spaceScale']+c['origin'],v)))
a=np.concatenate(rows);a=a[np.argsort(a[:,0])].astype('<f4');a.tofile(out/'source.f32');print('Body source',len(a),flush=True)
# Signed-distance approximation to the rounded source volume. No force acts
# inside it; the smooth outside potential is applied before pressure projection.
nx,ny,nz=c['nx']+1,c['ny']+1,c['nz']+1
x=(np.arange(nx)*c['h']-c['origin'][0])/c['spaceScale'];z=(np.arange(ny)*c['h']-c['origin'][1])/c['spaceScale'];y=(np.arange(nz)*c['h']-c['origin'][2])/c['spaceScale']
xx,zz=np.meshgrid(x,z,indexing='ij');d,depth,center=properties(xx.ravel(),zz.ravel());d=d.reshape(nx,ny);depth=depth.reshape(nx,ny);center=center.reshape(nx,ny)
sdf=np.minimum(d[:,:,None],depth[:,:,None]-abs(y[None,None,:]-center[:,:,None])).astype(np.float32)*c['spaceScale'];sdf=gaussian_filter(sdf,.55)
grad=np.gradient(sdf,c['h']);norm=np.maximum(.1,np.sqrt(sum(g*g for g in grad)));outside=np.maximum(0,-sdf);band=np.exp(-(outside/.16)**2)
for axis in range(3):
 n=grad[axis]/norm;force=160*outside*n*band;damping=5*n*n*band
 # Same staggered samples as the native MAC layout.
 for j in range(3):
  if j!=axis:
   force=.5*(force+np.roll(force,-1,axis=j));damping=.5*(damping+np.roll(damping,-1,axis=j))
 np.stack((force,damping),axis=-1).astype('<f4').tofile(out/f'guide-{axis}.f32')
np.savez_compressed(out/'body-sdf.npz',sdf=sdf)
report=dict(particles=len(a),source='Single lattice filling the approved 02 signed-distance volume with rounded depth',medianSpeed=float(np.median(np.linalg.norm(a[:,4:],axis=1))),writeEnds=float(a[:,0].max()),holdUntil=5.8,releaseEnds=6.65,forceBoundary='Zero force in the full rounded volume; smooth exterior bending force with radial damping; before native pressure projection',iteration=3)
(out/'source-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
