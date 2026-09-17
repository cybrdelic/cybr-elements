"""CPU incompressible humid-air solver driven by a solved cold ice surface.

Velocity and temperature are advected; spectral pressure projection removes
divergence. Supersaturation creates liquid fog and undersaturation evaporates
it. Ice is a maintained cold boundary in this short hold study. Air-to-ice heat
is measured so the size of the omitted mechanical backreaction is explicit.
"""
from pathlib import Path
import os,sys,time,json,argparse
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np,psutil
from scipy.ndimage import gaussian_filter,map_coordinates
from scipy.fft import fftn,ifftn,fftfreq
R=Path(__file__).resolve().parent

def saturation(t):
 c=np.clip(t-273.15,-55,55);pressure=610.94*np.exp(17.625*c/(c+243.04));return .622*pressure/(101325-pressure)

def project(velocity,dx):
 kk=np.meshgrid(*[2*np.pi*fftfreq(n,d=dx) for n in velocity.shape[:3]],indexing='ij');den=sum(k*k for k in kk);den[0,0,0]=1
 spectrum=[fftn(velocity[...,j],workers=1) for j in range(3)];dot=sum(kk[j]*spectrum[j] for j in range(3));before=float(np.sqrt(np.mean(np.abs(dot)**2)))
 for j in range(3):spectrum[j]-=kk[j]*dot/den
 after=float(np.sqrt(np.mean(np.abs(sum(kk[j]*spectrum[j] for j in range(3)))**2)))
 return np.stack([ifftn(q,workers=1).real for q in spectrum],axis=-1),before,after

def run(frame=61,steps=72):
 proc=psutil.Process();proc.cpu_affinity(proc.cpu_affinity()[:2]);start=time.time();source=R/'cache/ice'/f'{frame:04}.npz';a=np.load(source);p=a['p'];temp=a['temperature'];dx=.075;lo=np.array([-4.5,-1.5,-.9]);shape=(104,40,76);coords=np.indices(shape,dtype='f4');counts=np.zeros(shape,dtype='f4');energy=counts.copy();index=np.floor((p-lo)/dx).astype(int);valid=((index>=1)&(index<np.array(shape)-1)).all(1);ii=index[valid];np.add.at(counts,tuple(ii.T),1);np.add.at(energy,tuple(ii.T),temp[valid]);weight=gaussian_filter(counts,1.2);target=gaussian_filter(energy,1.2)/np.maximum(weight,1e-9);coupling=np.clip(weight/.22,0,1)*.12;coupling[target<230]=0;inside=weight>.75
 rng=np.random.default_rng(188);velocity=gaussian_filter(rng.normal(0,1,(*shape,3)),(2,2,2,0));velocity,_,_=project(velocity,dx);velocity*=.025/max(float(np.std(velocity)),1e-8)
 air=np.full(shape,293.15);vapor=np.full(shape,float(saturation(293.15))*.72);fog=np.zeros(shape);initial_water=float(vapor.sum());heat_to_body=0.;stats=[];dt=1/30
 for f in range(steps):
  back=coords-np.moveaxis(velocity,-1,0)*dt/dx
  velocity=np.stack([map_coordinates(velocity[...,j],back,order=1,mode='nearest') for j in range(3)],axis=-1)
  air=map_coordinates(air,back,order=1,mode='nearest');vapor=map_coordinates(vapor,back,order=1,mode='nearest');fog=map_coordinates(fog,back,order=1,mode='nearest')
  exchange=(air-target)*coupling;air-=exchange;heat_to_body+=float(exchange.sum()*1.2*1005*dx**3)
  # Condensation warms the air; evaporation cools it. Amount is limited by
  # saturation and available liquid instead of fading an opacity field.
  excess=vapor-saturation(air);change=np.where(excess>0,excess*.12,-np.minimum(fog,-excess*.08));vapor-=change;fog+=change;air+=change*2.26e6/1005
  velocity[...,2]+=9.81*(air-293.15)/293.15*dt;velocity*=np.exp(-dt*.12);velocity[inside]*=.1;velocity,before,after=project(velocity,dx)
  assert np.isfinite(velocity).all() and fog.min()>-1e-10;stats.append({'step':f,'projectionResidualRatio':after/max(before,1e-20),'maxSpeed':float(np.linalg.norm(velocity,axis=-1).max()),'fogWaterKg':float(fog.sum()*1.2*dx**3)})
  if f%24==0:print('Cold vapor',f,'fog kg',round(stats[-1]['fogWaterKg'],5),'seconds',round(time.time()-start,1),flush=True)
  if time.time()-start>95:raise RuntimeError('CPU vapor budget reached')
 # Mie extinction estimate for 7-micrometre droplets; resolved density has
 # physical units rather than a free artistic opacity multiplier.
 sigma=3*(fog*1.2)/(2*1000*7e-6);sigma[inside]=0;out=R/'cache/ice';np.savez_compressed(out/f'vapor-{frame:04}.npz',sigma=sigma.astype('f4'),temperature=air.astype('f4'),velocity=velocity.astype('f4'),origin=lo,dx=dx)
 body_mass=float(len(p)*float(a['volume'])*1000);report={'solver':'3D Eulerian advection + spectral pressure projection + humidity phase exchange','device':'CPU','seconds':round(time.time()-start,3),'grid':list(shape),'steps':steps,'heatTransferredToIceJ':heat_to_body,'fractionOfBodyLatentHeat':heat_to_body/max(body_mass*334000,1e-8),'waterTransportRelativeError':float((vapor+fog).sum()/initial_water-1),'maximumExtinctionPerM':float(sigma.max()),'projectionWorstRatio':max(q['projectionResidualRatio'] for q in stats),'limits':'Short held-surface study; ice boundary temperature is prescribed by the primary solve. Semi-Lagrangian water transport is not exactly conservative.','history':stats};(out/f'vapor-{frame:04}.json').write_text(json.dumps(report,indent=2));print('COLD_VAPOR',report['seconds'],flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--frame',type=int,default=61);ap.add_argument('--steps',type=int,default=72);a=ap.parse_args();run(a.frame,a.steps)
