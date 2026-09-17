"""CPU incompressible advection for the three new local atmospheres.

Periodic FFT pressure projection with padded, absorbing outer boundaries.
Authored emission/curl force, semi-Lagrangian transport, buoyancy, dissipation.
PNG atlases retain the 3D density; they are sampled as a volume in Cycles.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='2'
from pathlib import Path
import numpy as np,json,sys
from scipy.ndimage import map_coordinates,gaussian_filter
from scipy.fft import rfftn,irfftn
from PIL import Image
R=Path(__file__).resolve().parent;O=R/'sigil-02-active-elements'
kind=sys.argv[1];assert kind in ['ice','lava','lightning']
out=O/kind/'density';out.mkdir(parents=True,exist_ok=True)
shape=(112,36,108 if kind=='lava' else 72);lo=np.array([-5.5,-1.8,0.]);extent=np.array([11.,3.6,8.1 if kind=='lava' else 5.4]);dx=extent/shape
q=np.indices(shape,dtype=np.float32);xyz=lo[:,None,None,None]+(q+.5)*dx[:,None,None,None]
src=np.load(R/'sigil-02-v2/source.npz');a=src['sdf'];z=(xyz[2]-src['lo'][2])/src['extent'][2]*(a.shape[0]-1);x=(xyz[0]-src['lo'][0])/src['extent'][0]*(a.shape[1]-1)
distance=map_coordinates(a,[z,x],order=1,mode='constant',cval=-2)
source=np.exp(-(np.maximum(0,-distance)/.20)**2)*np.exp(-(xyz[1]/.43)**2)
source*=np.clip((distance+.28)/.28,0,1)
edge=np.prod([np.clip(np.minimum(q[i],shape[i]-1-q[i])/5,0,1) for i in range(3)],axis=0)
freq=[2*np.pi*np.fft.fftfreq(shape[i],d=dx[i]) for i in range(2)]+[2*np.pi*np.fft.rfftfreq(shape[2],d=dx[2])]
k=np.meshgrid(*freq,indexing='ij');k2=sum(v*v for v in k);k2[0,0,0]=1
v=np.zeros((3,*shape),np.float32);density=np.zeros(shape,np.float32);temp=density.copy();dt=1/60
rng=np.random.default_rng(721);seed=gaussian_filter(rng.normal(size=shape).astype('f'),2);seed/=seed.std()
trajectories=None
if kind in ['ice','lava']:
 trajectories=np.load(O/kind/'rigid-trajectories.npz')['poses'];geometry=json.loads((R/'sigil-02-coherent/earth-geometry.json').read_text())['pieces'];local=[];owners=[]
 for owner,row in enumerate(geometry):
  vertices=np.array(row['verts'],np.float32)[::max(1,len(row['verts'])//30)];vertices[:,1]*=1.65 if kind=='ice' else 2.2;local.extend(vertices);owners.extend([owner]*len(vertices))
 local=np.array(local,np.float32);owners=np.array(owners);referenceSourceMass=source.sum()
rows=[]
for f in range(300):
 t=f/30
 if trajectories is not None:
  pose=trajectories[f,owners];qv=pose[:,4:];twice=2*np.cross(qv,local);world=local+pose[:,3:4]*twice+np.cross(qv,twice)+pose[:,:3]
  ijk=np.rint((world-lo)/dx-.5).astype(int);valid=np.all((ijk>=0)&(ijk<shape),axis=1);ijk=ijk[valid];body=np.zeros(shape,np.float32);np.add.at(body,tuple(ijk.T),1)
  body=gaussian_filter(body,(1.3,1.3,1.3),mode='constant');source=np.minimum(1,body*referenceSourceMass/max(float(body.sum()),1e-5))
 for sub in range(2):
  back=q-v*dt/dx[:,None,None,None]
  v=np.stack([map_coordinates(v[i],back,order=1,mode='constant') for i in range(3)])
  density=map_coordinates(density,back,order=1,mode='constant')
  temp=map_coordinates(temp,back,order=1,mode='constant')
  envelope=np.clip((t-.2)/1.8,0,1)*(np.exp(-max(0,t-5.5)*.35) if kind=='lava' else np.exp(-max(0,t-6.8)*.25) if kind=='ice' else np.clip((8.4-t)/1.2,0,1))
  rate={'ice':.16,'lava':.28,'lightning':.58}[kind]
  noise=np.maximum(.0,.6+.45*np.sin(xyz[0]*3.2+xyz[2]*4.8+t*.8)+seed*.22)
  emission=source*noise*rate*envelope
  density+=emission*dt;temp+=emission*dt*2
  density*=np.exp(-dt*({'ice':.55,'lava':.32,'lightning':.28}[kind]));temp*=np.exp(-dt*.6)
  v[2]+=dt*(temp*({'ice':-1.0,'lava':2.2,'lightning':.6}[kind]))
  v[0]+=dt*.24*np.sin(xyz[2]*2.1+t*.5)*np.cos(xyz[1]*3.1)
  v[1]+=dt*.18*np.sin(xyz[0]*2.8-t*.4)*np.cos(xyz[2]*2.1)
  # Fourier-space Helmholtz projection, not a decorative density warp.
  vh=[rfftn(v[i],workers=2) for i in range(3)];div=sum(k[i]*vh[i] for i in range(3))
  v=np.stack([irfftn(vh[i]-k[i]*div/k2,s=shape,workers=2).real for i in range(3)]).astype('f')
  v*=edge[None];density*=edge;temp*=edge
 assert np.isfinite(v).all() and np.isfinite(density).all()
 nz=shape[2];atlas=np.zeros((nz*6,112*6),np.uint8)
 for layer in range(36):atlas[(layer//6)*nz:(layer//6+1)*nz,(layer%6)*112:(layer%6+1)*112]=np.rint(np.clip(density[:,layer,:].T/1.2,0,1)*255).astype('uint8')
 Image.fromarray(np.flipud(atlas)).save(out/f'{f:04}.png',compress_level=2)
 if f%30==0:rows.append(dict(frame=f,maxDensity=float(density.max()),densitySum=float(density.sum()),maxSpeed=float(np.linalg.norm(v,axis=0).max())));print(kind,f,flush=True)
(out.parent/'atmosphere.json').write_text(json.dumps(dict(grid=shape,lo=lo.tolist(),extent=extent.tolist(),frames=300,finite=True,emitterCoupling='Actual per-frame Bullet/kinematic fracture transforms' if trajectories is not None else 'Approved 02 charge domain',method=__doc__,rows=rows),indent=2))
