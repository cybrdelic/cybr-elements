"""Water-only moving-inlet study; retain the previous released film unchanged."""
from pathlib import Path
import json, shutil, sys
import numpy as np
from scipy.ndimage import map_coordinates, gaussian_filter, distance_transform_edt
from skimage.morphology import medial_axis

R=Path(__file__).resolve().parent
full='--full' in sys.argv
O=R/'sigil-02-water-arrival'/('full' if full else ''); O.mkdir(exist_ok=True)
h=.018 if full else .027
cfg=dict(h=h,nx=round(4.212/h),ny=round(2.88/h),nz=round(.864/h),origin=[2.1,.98,.432],spaceScale=.35,timeScale=.4)
cfg['extent']=[cfg[k]*h for k in ['nx','ny','nz']]
(O/'config.json').write_text(json.dumps(cfg,indent=2))
(O/'contract.json').write_text(json.dumps(dict(scope='Water 02 formation only; preserve r3 hold, material and every other element',defect='Fluid was born at its finished position with negligible travel, making a mechanical left-to-right wipe',change='Curved inlets start upstream along the stroke tangents. Increased tangential source momentum carries the fluid into the mark; normal damping catches overshoot. Native pressure, free surface and parcel motion remain active.',limits='Authored static bending potential and momentum damping, not unforced natural formation of typography. No particle teleporting, animated guide pose or render-only morph.',iterations=4,capture='CPU native simulation, reconstruction, reduced Cycles motion frames; full render only after visual review',gates=['Finite and converged native solve','Conserved source volume','Visible transport before settling','Retained full silhouette and long hold','No point-cloud droplets','Black backdrop'],baseline='baseline-formation.jpg'),indent=2))
src=dict(np.load(R/'sigil-02-v2/source.npz')); lo=src['lo'];ext=src['extent'];shape=src['sdf'].shape
skel,dist=medial_axis(src['sdf']>0,return_distance=True,rng=1871)
nearest=distance_transform_edt(~skel,return_distances=False,return_indices=True)
src['local_radius']=np.maximum(.025,dist[tuple(nearest)]*ext[0]/(shape[1]-1))
def sample(name,x,z):
 return map_coordinates(src[name],[(z-lo[2])/ext[2]*(shape[0]-1),(x-lo[0])/ext[0]*(shape[1]-1)],order=1,mode='constant',cval=-2 if name=='sdf' else 0)
def properties(x,z):
 d=sample('sdf',x,z);r=sample('local_radius',x,z)
 return d,np.sqrt(np.maximum(0,d*(2*r-d)))*1.1,.20*np.sin(x*1.25)+.055*np.sin(x*2.1+z*1.7)
spacing=h*.5/cfg['spaceScale'];rng=np.random.default_rng(6415)
x,z=np.meshgrid(np.arange(-4.08,4.09,spacing),np.arange(.42,3.5,spacing));x=x.ravel();z=z.ravel();d,depth,center=properties(x,z);keep=d>0;x=x[keep];z=z[keep];depth=depth[keep];center=center[keep]
rows=[]
for y in np.arange(-.38,.381,spacing):
 keep=abs(y)<depth;a=x[keep];b=z[keep];cy=center[keep]
 if not len(a):continue
 birth=.25+(np.clip(sample('arrival',a,b),.30,3.90)-.30)/3.60*1.85+.08*(1-np.clip(sample('sdf',a,b)/sample('local_radius',a,b),0,1))
 # Backtrace the inlet along each curved stroke. Momentum now follows the
 # stroke tangent rather than translating a slice horizontally.
 tx=sample('dirx',a,b);tz=sample('dirz',a,b);norm=np.maximum(.01,np.hypot(tx,tz));tx/=norm;tz/=norm
 p=np.column_stack((a-tx*.27,b-tz*.27,cy+y))
 speed=.30*(1+.12*np.sin(a*4+b*2))
 v=np.column_stack((tx*speed-tz*y*.22,tz*speed+tx*y*.22,.20*np.cos(a*1.25)*tx*speed))
 p+=rng.uniform(-spacing*.1,spacing*.1,p.shape)
 rows.append(np.column_stack((birth,p*.35+cfg['origin'],v)))
a=np.concatenate(rows);a=a[np.argsort(a[:,0])].astype('<f4');a.tofile(O/'source.f32');source_rows=a.copy()
assert np.all(a[:,1:4]>h) and np.all(a[:,1:4]<np.array(cfg['extent'])-h)
# Static full-volume bending potential. The inlet carries tangential momentum;
# separate curl forces sustain circulation without moving a guide pose.
nx,ny,nz=cfg['nx']+1,cfg['ny']+1,cfg['nz']+1
x=(np.arange(nx)*h-cfg['origin'][0])/.35;z=(np.arange(ny)*h-cfg['origin'][1])/.35;y=(np.arange(nz)*h-cfg['origin'][2])/.35
xx,zz=np.meshgrid(x,z,indexing='ij');d,depth,center=properties(xx.ravel(),zz.ravel());d=d.reshape(nx,ny);depth=depth.reshape(nx,ny);center=center.reshape(nx,ny)
sdf=gaussian_filter(np.minimum(d[:,:,None],depth[:,:,None]-abs(y[None,None,:]-center[:,:,None])).astype(np.float32)*.35,.55)
grad=np.gradient(sdf,h);norm=np.maximum(.1,np.sqrt(sum(g*g for g in grad)));outside=np.maximum(0,-sdf);band=np.exp(-(outside/.32)**2)
for axis in range(3):
 n=grad[axis]/norm;force=160*outside*n*band;damping=24*n*n*band
 for j in range(3):
  if j!=axis:force=.5*(force+np.roll(force,-1,axis=j));damping=.5*(damping+np.roll(damping,-1,axis=j))
 np.stack((force,damping),axis=-1).astype('<f4').tofile(O/f'guide-{axis}.f32')
# Two smooth solenoidal force bases keep bulk liquid circulating during the
# hold. Curl of a vector potential, localized to the actual liquid domain;
# pressure still resolves the resulting flow. This is an authored bending
# force, not an optical animation or a direct particle-position constraint.
xx,zz,yy=np.meshgrid(np.arange(nx)*h,np.arange(ny)*h,np.arange(nz)*h,indexing='ij')
mask=np.exp(-(np.maximum(0,-sdf)/.055)**2)
bases=[]
for phase in [0.,1.73]:
 pot=[mask*np.sin(13*zz+9*yy+phase)*np.cos(8*xx-phase),
      mask*np.sin(11*yy+7*xx-phase)*np.cos(10*zz+phase),
      mask*np.sin(12*xx+8*zz+phase)*np.cos(9*yy-phase)]
 curl=[np.gradient(pot[2],h,axis=1)-np.gradient(pot[1],h,axis=2),
       np.gradient(pot[0],h,axis=2)-np.gradient(pot[2],h,axis=0),
       np.gradient(pot[1],h,axis=0)-np.gradient(pot[0],h,axis=1)]
 magnitude=np.sqrt(sum(v*v for v in curl));normalizer=max(.01,float(np.percentile(magnitude[sdf>0],90)))
 bases.append([v/normalizer for v in curl])
for axis in range(3):
 fields=[]
 for basis in bases:
  a=basis[axis]
  for j in range(3):
   if j!=axis:a=.5*(a+np.roll(a,-1,axis=j))
  fields.append(a)
 np.stack(fields,axis=-1).astype('<f4').tofile(O/f'circulation-{axis}.f32')
shutil.copy2(R/'sigil-02-water-hold/guides.npz',O/'guides.npz')
report=dict(particles=len(source_rows),grid=[cfg['nx'],cfg['ny'],cfg['nz']],sourceStart=float(source_rows[:,0].min()),sourceEnd=float(source_rows[:,0].max()),sourceSpeedMedian=float(np.median(np.linalg.norm(source_rows[:,4:],axis=1))),initialUpstreamDistance=.27,holdUntil=5.8,render='Existing r3 water optics, unchanged',heldMotion='Two divergence-free curl-force bases drive resolved circulation after 2.3s')
(O/'source-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
