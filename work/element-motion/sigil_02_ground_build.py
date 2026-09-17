"""Closed-mass water study: a visible ground ribbon is lifted into the 02 sigil."""
from pathlib import Path
import json, sys, shutil
import numpy as np
from scipy.ndimage import map_coordinates, gaussian_filter, distance_transform_edt
from skimage.morphology import medial_axis
R=Path(__file__).resolve().parent
full='--full' in sys.argv
O=R/'sigil-02-bending-ground'/('full' if full else 'cpu');O.mkdir(parents=True,exist_ok=True)
h=.018 if full else .032
cfg=dict(h=h,nx=round(4.752/h),ny=round(1.908/h),nz=round(3.024/h),origin=[2.376,.252,1.512],spaceScale=.35,timeScale=.4,frames=390,floorWorld=0)
cfg['extent']=[cfg[k]*h for k in ['nx','ny','nz']]
(O/'config.json').write_text(json.dumps(cfg,indent=2))
src=dict(np.load(R/'sigil-02-v2/source.npz'));lo=src['lo'];ext=src['extent'];shape=src['sdf'].shape
skel,dist=medial_axis(src['sdf']>0,return_distance=True,rng=1871)
nearest=distance_transform_edt(~skel,return_distances=False,return_indices=True)
src['radius']=np.maximum(.025,dist[tuple(nearest)]*ext[0]/(shape[1]-1))
def sample(name,x,z):
 return map_coordinates(src[name],[(z-lo[2])/ext[2]*(shape[0]-1),(x-lo[0])/ext[0]*(shape[1]-1)],order=1,mode='constant',cval=-2 if name=='sdf' else 0)
def properties(x,z):
 d=sample('sdf',x,z);r=sample('radius',x,z)
 return d,np.sqrt(np.maximum(0,d*(2*r-d)))*1.1,.20*np.sin(x*1.25)+.055*np.sin(x*2.1+z*1.7)
spacing=h*.5/.35;rng=np.random.default_rng(6415)
x,z=np.meshgrid(np.arange(-4.08,4.09,spacing),np.arange(.42,3.5,spacing));x=x.ravel();z=z.ravel();d,depth,center=properties(x,z);keep=d>0;x=x[keep];z=z[keep];depth=depth[keep];center=center[keep]
parts=[]
for y in np.arange(-.38,.381,spacing):
 keep=abs(y)<depth
 if np.any(keep):parts.append(np.column_stack((x[keep],z[keep],center[keep]+y)))
target=np.concatenate(parts);target+=rng.uniform(-spacing*.08,spacing*.08,target.shape)
# Equal-mass longitudinal bins and conditional vertical/depth ranks map the
# complete material volume into one connected ribbon. No timed emitters.
order=np.argsort(target[:,0],kind='stable');target=target[order];N=len(target)
u=(np.arange(N)+.5)/N;cross=np.empty((N,2));bins=np.array_split(np.arange(N),max(32,round(5.4/spacing)))
vertical=np.linspace(-1,1,4097);cdf=(vertical*np.sqrt(np.maximum(0,1-vertical**2))+np.arcsin(vertical)+np.pi/2)/np.pi
for indices in bins:
 local=indices[np.argsort(target[indices,1],kind='stable')]
 vz=np.interp((np.arange(len(local))+.5)/len(local),cdf,vertical)
 cross[local,0]=vz
 for slab in np.array_split(local,max(2,round(.56/spacing))):
  dep=slab[np.argsort(target[slab,2],kind='stable')]
  cross[dep,1]=(2*(np.arange(len(dep))+.5)/len(dep)-1)*np.sqrt(np.maximum(0,1-cross[dep,0]**2))
volume=N*spacing**3;length=volume/(np.pi*.28*.50)
initial=np.column_stack((-3.65+length*u,.32+.28*cross[:,0],.38*np.sin(u*2*np.pi)+.50*cross[:,1]))
initial+=rng.uniform(-spacing*.05,spacing*.05,initial.shape)
rows=np.column_stack((initial*.35+cfg['origin'],target*.35+cfg['origin'],u,cross)).astype('<f4')
rows.tofile(O/'parcels.f32')
assert np.all(rows[:,:3]>h) and np.all(rows[:,:3]<np.array(cfg['extent'])-h)
# Only the hold uses a static full-volume bending field. The approach uses
# bounded external accelerations toward moving material guides, then blends
# out those per-parcel guides so pressure and circulation remain free.
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
old_guides=np.load(R/'sigil-02-water-hold/guides.npz')
np.savez_compressed(O/'guides.npz',points=old_guides['points']+np.array(cfg['origin'])-np.array([2.1,.98,.432]),radii=old_guides['radii'])
report=dict(particles=N,grid=[cfg['nx'],cfg['ny'],cfg['nz']],massBornAtStart=True,source='Single continuous ground ribbon',ribbonLength=length,worldVolume=volume,releaseAt=8.1,duration=13,floor='Native solid box at world height zero; no outflow deletion',limits='The bending force is authored. Liquid transport, pressure, free surface, gravity and floor contact are solved; no render morph or particle position assignment.')
(O/'source-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
