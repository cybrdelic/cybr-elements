"""CPU lava material study: dense fluid projection and temperature viscosity.

The study is a viscous advancing lobe on a contact plane, not another tube.
It uses a position-based incompressibility approximation, implicit neighbor
viscosity, and heat exchange. Fine crust morphology is a separate advected
surface model, not a claim of resolved microscopic solid mechanics.
"""
from pathlib import Path
import os,time,json,argparse
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['NUMBA_NUM_THREADS']='2';os.environ['CUDA_VISIBLE_DEVICES']='-1'
import numpy as np,psutil
from numba import njit
R=Path(__file__).resolve().parent/'lava-focus'

@njit(cache=True)
def neighbors(x,h):
 lo=np.empty(3);hi=np.empty(3)
 for axis in range(3):
  lo[axis]=x[0,axis];hi[axis]=x[0,axis]
  for i in range(len(x)):lo[axis]=min(lo[axis],x[i,axis]);hi[axis]=max(hi[axis],x[i,axis])
 lo-=h*2;shape=np.ceil((hi-lo)/h).astype(np.int32)+3
 head=np.full(shape[0]*shape[1]*shape[2],-1,np.int32);link=np.full(len(x),-1,np.int32);cell=np.floor((x-lo)/h).astype(np.int32)
 for i in range(len(x)):
  a,b,c=cell[i];ix=(a*shape[1]+b)*shape[2]+c;link[i]=head[ix];head[ix]=i
 near=np.full((len(x),150),-1,np.int32);count=np.zeros(len(x),np.int32);overflow=0
 for i in range(len(x)):
  a,b,c=cell[i]
  for aa in range(max(0,a-1),min(shape[0],a+2)):
   for bb in range(max(0,b-1),min(shape[1],b+2)):
    for cc in range(max(0,c-1),min(shape[2],c+2)):
     j=head[(aa*shape[1]+bb)*shape[2]+cc]
     while j>=0:
      d0=x[i,0]-x[j,0];d1=x[i,1]-x[j,1];d2=x[i,2]-x[j,2]
      if i!=j and d0*d0+d1*d1+d2*d2<h*h:
       if count[i]<150:near[i,count[i]]=j;count[i]+=1
       else:overflow+=1
      j=link[j]
 return near,count,overflow

@njit(cache=True)
def density_lambdas(x,near,count,h,vol):
 n=len(x);lam=np.zeros(n);density=np.zeros(n);coef=315/(64*np.pi*h**9);spiky=-45/(np.pi*h**6)
 for i in range(n):
  rho=vol*coef*h**6;g0=0.;g1=0.;g2=0.;grad2=0.
  for k in range(count[i]):
   j=near[i,k];d0=x[i,0]-x[j,0];d1=x[i,1]-x[j,1];d2=x[i,2]-x[j,2];r2=d0*d0+d1*d1+d2*d2
   if r2>=h*h or r2<1e-14:continue
   distance=np.sqrt(r2);rho+=vol*coef*(h*h-r2)**3;factor=vol*spiky*(h-distance)**2/distance;a=factor*d0;b=factor*d1;c=factor*d2;g0+=a;g1+=b;g2+=c;grad2+=a*a+b*b+c*c
  C=max(-.008,rho-1.);lam[i]=-C/(grad2+g0*g0+g1*g1+g2*g2+1e-5);density[i]=rho
 return lam,density

@njit(cache=True)
def project(x,near,count,h,vol,lam):
 delta=np.zeros_like(x);spiky=-45/(np.pi*h**6);limit=.09*h
 for i in range(len(x)):
  a=0.;b=0.;c=0.
  for k in range(count[i]):
   j=near[i,k];d0=x[i,0]-x[j,0];d1=x[i,1]-x[j,1];d2=x[i,2]-x[j,2];r2=d0*d0+d1*d1+d2*d2
   if r2>=h*h or r2<1e-14:continue
   distance=np.sqrt(r2);s_corr=-.00003*h*h*((1-r2/(h*h))/.91)**12;factor=(lam[i]+lam[j]+s_corr)*vol*spiky*(h-distance)**2/distance;a+=factor*d0;b+=factor*d1;c+=factor*d2
  norm=np.sqrt(a*a+b*b+c*c);scale=min(1.,limit/max(norm,1e-12));delta[i,0]=a*scale;delta[i,1]=b*scale;delta[i,2]=c*scale
 return x+delta

@njit(cache=True)
def transport(x,v,temp,near,count,h,dt,reference_neighbors):
 n=len(x);rhs=v.copy();new=v.copy();coeff=np.zeros(n);surface=np.zeros(n);heat=temp.copy()
 for i in range(n):
  surface[i]=min(1.,max(0.,1-count[i]/reference_neighbors));eta=min(18000.,90*np.exp(20000*(1/max(850.,temp[i])-1/1450.)));coeff[i]=dt*eta/(2700*h*h)*6
  # A surface parcel stands for a thin thermal boundary layer. Enhanced
  # heat extraction is explicitly part of the bending effect.
  radiation=.94*5.670374419e-8*(temp[i]**4-293.15**4);rate=surface[i]*(radiation+160000)/(2700*1200*.004);heat[i]=max(1050.,temp[i]-dt*rate)
 # Backward Euler neighbor Laplacian. Pair conductance is symmetric.
 for iteration in range(8):
  for i in range(n):
   s0=rhs[i,0];s1=rhs[i,1];s2=rhs[i,2];total=1.
   for k in range(count[i]):
    j=near[i,k];d0=x[i,0]-x[j,0];d1=x[i,1]-x[j,1];d2=x[i,2]-x[j,2];q=1-(d0*d0+d1*d1+d2*d2)/(h*h)
    if q<=0:continue
    w=.5*(coeff[i]+coeff[j])*q*q/max(1.,reference_neighbors*.27);s0+=w*v[j,0];s1+=w*v[j,1];s2+=w*v[j,2];total+=w
   new[i,0]=s0/total;new[i,1]=s1/total;new[i,2]=s2/total
  v[:]=new
 # Symmetric, conservative heat transfer between nearby parcels.
 for i in range(n):
  for k in range(count[i]):
   j=near[i,k]
   if j<=i:continue
   q=dt*.06*(temp[j]-temp[i])/max(reference_neighbors,1.);heat[i]+=q;heat[j]-=q
 return v,heat,surface

def main(steps=90):
 start=time.time();proc=psutil.Process();proc.cpu_affinity(proc.cpu_affinity()[:2]);rng=np.random.default_rng(819);spacing=.024;h=spacing*2.45
 grid=np.stack(np.meshgrid(np.arange(-.95,.72,spacing),np.arange(-.48,.48,spacing),np.arange(.018,.58,spacing),indexing='ij'),axis=-1).reshape(-1,3)
 bodies=[([-.32,.015,.20],[.62,.29,.18]),([-.74,-.02,.33],[.30,.22,.22]),([.27,.02,.145],[.39,.30,.12])];inside=np.zeros(len(grid),bool)
 for center,radii in bodies:inside|=(((grid-np.array(center))/radii)**2).sum(1)<1
 x=grid[inside]+rng.uniform(-.07,.07,(int(inside.sum()),3))*spacing;rest=x.copy();v=np.zeros_like(x);v[:,0]=.46*np.clip((.65-x[:,0])/1.5,.1,1);v[:,1]=-.10*x[:,1];v[:,2]=-.12*np.clip(x[:,2]-.25,0,1)
 temp=1460-85*np.clip((x[:,0]+.85)/1.55,0,1);vol=spacing**3;near,count,overflow=neighbors(x,h);reference=float(np.percentile(count,90));lam,rho=density_lambdas(x,near,count,h,vol);interior=count>reference*.9;vol/=float(np.median(rho[interior]));rows=[];dt=1/90;R.mkdir(exist_ok=True)
 print('START',len(x),'particles; reference neighbors',reference,flush=True)
 for frame in range(steps):
  old=x.copy();v[:,2]-=9.81*dt;x+=v*dt;x[:,2]=np.maximum(x[:,2],.012);near,count,overflow=neighbors(x,h*1.12);assert overflow==0,('neighbor truncation',overflow)
  for iteration in range(7):
   lam,rho=density_lambdas(x,near,count,h,vol);x=project(x,near,count,h,vol,lam);x[:,2]=np.maximum(x[:,2],.012)
  v=(x-old)/dt;v,temp,surface=transport(x,v,temp,near,count,h,dt,reference);contact=x[:,2]<.016;v[contact,:2]*=.80
  assert np.isfinite(x).all() and np.linalg.norm(v,axis=1).max()<12
  if frame%15==0 or frame==steps-1:
   row={'step':frame,'densityP95':float(np.quantile(rho,.95)),'maxSpeed':float(np.linalg.norm(v,axis=1).max()),'temperatureRange':[float(temp.min()),float(temp.max())],'seconds':round(time.time()-start,2)};rows.append(row);print('FLOW',json.dumps(row),flush=True)
  if frame in [0,29,59,89] or frame==steps-1:np.savez_compressed(R/f'flow-{frame:04}.npz',p=x.astype('f4'),v=v.astype('f4'),rest=rest.astype('f4'),temperature=temp.astype('f4'),surface=surface.astype('f4'),volume=vol,spacing=spacing)
  if time.time()-start>105:raise RuntimeError('CPU flow study time budget reached')
 report={'solver':'CPU position-based incompressibility and implicit temperature-dependent viscosity','particles':len(x),'steps':steps,'seconds':round(time.time()-start,2),'restVolume':len(x)*vol,'densityKgM3':2700,'neighborOverflow':overflow,'history':rows,'limits':['A reduced PBF fluid, not a full validated Navier-Stokes/solidification solver','The study uses a physical contact plane; no plane is visible to the camera','Surface cooling includes an authored heat extraction term','Detailed crust is generated separately in advected material coordinates']};(R/'flow-report.json').write_text(json.dumps(report,indent=2));print('COMPLETE',report['seconds'],flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--steps',type=int,default=90);a=ap.parse_args();main(a.steps)
