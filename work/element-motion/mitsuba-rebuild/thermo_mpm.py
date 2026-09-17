"""Bounded 3-D CPU thermal MLS-MPM prototype, not a Houdini-equivalent solver.

This rebuilds particle motion instead of recoloring cached fluid meshes.
Enthalpy controls phase, density, deviatoric stress and viscosity. Heat moves
through mass-weighted grid exchanges. An explicit bending heat sink is tracked
as removed energy. Stiffness is reduced for this explicit CPU prototype; a
production ice solve requires an implicit elastic/projection step.
"""
from pathlib import Path
import os,sys,json,time,argparse
os.environ['NUMBA_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np,psutil
from numba import njit
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R.parent));from shared_motion import pose
from ice_constraints import network,advance as solid_step

@njit(cache=True)
def state(h,kind):
 if kind==0:
  if h<0:return 273.15+h/2100.,1.
  if h<334000:return 273.15,1-h/334000.
  return 273.15+(h-334000)/4180.,0.
 interval=1200.*190.+400000.
 if h<0:return 1150+h/1200.,1.
 if h<interval:return 1150+190*h/interval,1-h/interval
 return 1340+(h-interval)/1200.,0.

@njit(cache=True)
def weights(f):
 w=np.empty((3,3))
 for j in range(3):w[0,j]=.5*(1.5-f[j])**2;w[1,j]=.75-(f[j]-1)**2;w[2,j]=.5*(f[j]-.5)**2
 return w

@njit(cache=True)
def step(x,v,C,F,h,damage,birth,clock,dt,dx,origin,gm,gv,gh,gd,kind,pvol):
 gm[:]=0;gv[:]=0;gh[:]=0;gd[:]=0;I=np.eye(3);rho0=1000. if kind==0 else 2600.;mass=pvol*rho0
 for p in range(len(x)):
  if birth[p]>clock:continue
  temperature,solid=state(h[p],kind);fp=(I+dt*C[p])@F[p];U,s,V=np.linalg.svd(fp);s=np.maximum(.65,np.minimum(s,1.5));J=s[0]*s[1]*s[2]
  targetJ=rho0/((1-solid)*rho0+solid*(917. if kind==0 else 2800.))
  if solid<.03:fp=I*J**(1/3)
  else:
   logs=np.log(s);mean=logs.mean();dev=logs-mean;norm=np.sqrt(np.sum(dev*dev));yield_strain=.045 if kind==0 else .055+.12*(1-solid)
   if norm>yield_strain:
    if kind==0:damage[p]=min(.96,damage[p]+(norm-yield_strain)*.10)
    dev*=yield_strain/max(norm,1e-9);fp=U@np.diag(np.exp(mean+dev))@V
  F[p]=fp;rotation=U@V;mu=(65000. if kind==0 else 28000.)*solid**3*(1-damage[p]);bulk=35000. if kind==0 else 45000.
  stress=2*mu*(fp-rotation)@fp.T+I*(bulk*(J/targetJ-1)*J)
  if kind==1:
   # Backward-Euler relaxation of the viscous deviatoric rate avoids the
   # explicit viscosity instability as the cooling melt thickens.
   eta=min(8000.,80*np.exp(min(12.,24000*(1/max(800.,temperature)-1/1450))))
   strain=.5*(C[p]+C[p].T);strain-=I*np.trace(strain)/3
   stress+=2*eta*strain/(1+8*eta*dt/(rho0*dx*dx))
  affine=mass*C[p]-dt*pvol*4/dx**2*stress
  q=(x[p]-origin)/dx;base=np.floor(q-.5).astype(np.int32);fr=q-base;w=weights(fr)
  for i in range(3):
   for j in range(3):
    for k in range(3):
     a,b,c=base[0]+i,base[1]+j,base[2]+k
     if a<0 or b<0 or c<0 or a>=gm.shape[0] or b>=gm.shape[1] or c>=gm.shape[2]:continue
     weight=w[i,0]*w[j,1]*w[k,2];dp=(np.array([i,j,k])-fr)*dx;gm[a,b,c]+=weight*mass;gv[a,b,c]+=weight*(mass*v[p]+affine@dp);gh[a,b,c]+=weight*mass*h[p]
 for a in range(gm.shape[0]):
  for b in range(gm.shape[1]):
   for c in range(gm.shape[2]):
    m=gm[a,b,c]
    if m<=1e-12:continue
    gv[a,b,c]/=m;gh[a,b,c]/=m
    support=1-min(1.,max(0.,(clock-3.7)/.6));gv[a,b,c,2]-=9.81*(1-support)*dt;gv[a,b,c]*=np.exp(-dt*.45)
    if c<3 and gv[a,b,c,2]<0:gv[a,b,c,2]=0
    if a<3 and gv[a,b,c,0]<0:gv[a,b,c,0]=0
    if a>gm.shape[0]-4 and gv[a,b,c,0]>0:gv[a,b,c,0]=0
    if b<3 and gv[a,b,c,1]<0:gv[a,b,c,1]=0
    if b>gm.shape[1]-4 and gv[a,b,c,1]>0:gv[a,b,c,1]=0
 # Symmetric pair exchanges preserve total enthalpy in the transfer grid.
 for a in range(1,gm.shape[0]-1):
  for b in range(1,gm.shape[1]-1):
   for c in range(1,gm.shape[2]-1):
    if gm[a,b,c]<=1e-10:continue
    ta,_=state(gh[a,b,c],kind)
    for axis in range(3):
     aa,bb,cc=a+(axis==0),b+(axis==1),c+(axis==2)
     if gm[aa,bb,cc]<=1e-10:continue
     tb,_=state(gh[aa,bb,cc],kind);conductance=(2.2 if kind==0 else 1.6)*dx;energy=conductance*(tb-ta)*dt
     gd[a,b,c]+=energy/gm[a,b,c];gd[aa,bb,cc]-=energy/gm[aa,bb,cc]
 removed=0.;active_count=0
 for p in range(len(x)):
  if birth[p]>clock:continue
  active_count+=1;q=(x[p]-origin)/dx;base=np.floor(q-.5).astype(np.int32);fr=q-base;w=weights(fr);vv=np.zeros(3);cc0=np.zeros((3,3));delta_h=0.;localmass=0.
  for i in range(3):
   for j in range(3):
    for k in range(3):
     a,b,c=base[0]+i,base[1]+j,base[2]+k
     if a<0 or b<0 or c<0 or a>=gm.shape[0] or b>=gm.shape[1] or c>=gm.shape[2]:continue
     weight=w[i,0]*w[j,1]*w[k,2];vel=gv[a,b,c];vv+=weight*vel;cc0+=4/dx*weight*np.outer(vel,np.array([i,j,k])-fr);delta_h+=weight*gd[a,b,c];localmass+=weight*gm[a,b,c]
  temperature,solid=state(h[p],kind);exposure=min(1.,max(.05,1-localmass/(rho0*dx**3)))
  if kind==0:
   # The explicitly accounted bending sink is necessary to freeze a large
   # moving body on a cinematic time scale; it is not an opacity fade.
   sink=310000*exposure+max(0,temperature-248)*90*exposure/(rho0*dx)
  else:
   natural=(.94*5.670374419e-8*(temperature**4-293**4)+45*(temperature-293))/(rho0*dx);sink=exposure*(natural+150000)
  loss=sink*dt;before_h=h[p]+delta_h;h[p]=max(before_h-loss,-40000. if kind==0 else -100000.);removed+=(before_h-h[p])*mass
  v[p]=vv;C[p]=cc0;x[p]+=dt*vv
 return removed,active_count

def simulate(kind,frames=62,n=4000,substeps=12):
 pself=psutil.Process();pself.cpu_affinity(pself.cpu_affinity()[:2]);start=time.time();rng=np.random.default_rng(940);kid=0 if kind=='ice' else 1;birth=np.sort(rng.uniform(.08,1.68,n));x=np.zeros((n,3));v=x.copy()
 for i,t in enumerate(birth):
  pos,d,_,_=pose(float(t));a=rng.uniform(0,2*np.pi);radius=np.sqrt(rng.random())*(.10+.045*np.sin(t*12)**2);normal=np.array([-d[1],0,d[0]]);x[i]=[pos[0],0,pos[1]];x[i]+=normal*radius*np.cos(a);x[i,1]+=radius*np.sin(a);v[i]=np.array([d[0],0,d[1]])*.65
 rest=x.copy();h=np.full(n,334000+4180*5 if kid==0 else 1200*(1480-1150)+400000.);damage=np.zeros(n);C=np.zeros((n,3,3));F=np.tile(np.eye(3),(n,1,1));dx=.06;origin=np.floor((x.min(0)-[1,.5,1.2])/dx)*dx;shape=tuple((np.ceil((x.max(0)+[1,.5,1.0]-origin)/dx).astype(int)+1).tolist());gm=np.zeros(shape);gv=np.zeros((*shape,3));gh=gm.copy();gd=gm.copy();pvol=7*np.pi*.122**2/n;dt=1/(30*substeps);out=R/'cache'/kind;out.mkdir(parents=True,exist_ok=True);rows=[];removed=0.
 if kid==0:bonds,length,bond_status,freeze_temp,peak_strain=network(rest,birth)
 for f in range(frames):
  for sub in range(substeps):
   clock=(f+(sub+1)/substeps)/30;loss,count=step(x,v,C,F,h,damage,birth,clock,dt,dx,origin,gm,gv,gh,gd,kid,pvol);removed+=loss
  active=birth<=clock;temperatures=np.array([state(e,kid)[0] for e in h]);phase=np.array([state(e,kid)[1] for e in h]);
  if kid==0:
   solid_step(x,v,temperatures,phase,bonds,length,bond_status,freeze_temp,peak_strain,pvol*1000,1/30)
  J=np.linalg.det(F[active]);max_speed=float(np.linalg.norm(v[active],axis=1).max(initial=0));assert np.isfinite(x).all() and max_speed<35,('unstable',kind,f,max_speed)
  row={'frame':f,'active':int(active.sum()),'mass':float(active.sum()*pvol*(1000 if kid==0 else 2600)),'solidFraction':float(phase[active].mean()) if active.any() else 0,'maximumSpeed':max_speed,'Jrange':[float(J.min(initial=1)),float(J.max(initial=1))],'removedHeatJ':removed,'thermalEnergyJ':float(np.sum(h[active])*pvol*(1000 if kid==0 else 2600)),'enthalpyBalanceRelativeError':float(abs(np.sum(h[active])*pvol*(1000 if kid==0 else 2600)+removed-active.sum()*pvol*(1000 if kid==0 else 2600)*(334000+4180*5 if kid==0 else 1200*(1480-1150)+400000.))/max(active.sum()*pvol*(1000 if kid==0 else 2600)*(334000+4180*5 if kid==0 else 1200*(1480-1150)+400000.),1))};rows.append(row)
  if kid==0:row['solidBonds']=int((bond_status==1).sum());row['brokenBonds']=int((bond_status==2).sum())
  if f in [20,35,50,61,75,90] or f==frames-1:np.savez_compressed(out/f'{f:04}.npz',p=x[active].astype('f4'),v=v[active].astype('f4'),rest=rest[active].astype('f4'),temperature=temperatures[active].astype('f4'),phase=phase[active].astype('f4'),damage=damage[active].astype('f4'),F=F[active].astype('f4'),volume=pvol,birth=birth[active])
  if kid==0 and (f in [50,61,75,90] or f==frames-1):np.savez_compressed(out/f'bonds-{f:04}.npz',pairs=bonds,status=bond_status,restLength=length,peakStrain=peak_strain,temperatureAtFreeze=freeze_temp)
  if f%10==0:print(kind,f,'solid',round(row['solidFraction'],3),'speed',round(max_speed,2),'seconds',round(time.time()-start,1),flush=True)
  if time.time()-start>160:
   (out/'partial-report.json').write_text(json.dumps({'status':'budget_stop','history':rows},indent=2));raise RuntimeError('CPU simulation budget reached')
 report={'solver':'3D CPU thermal MLS-MPM prototype','device':'CPU','kind':kind,'seconds':round(time.time()-start,3),'particles':n,'dx':dx,'substeps':substeps,'grid':list(shape),'frames':rows,'limits':['Reduced explicit elastic stiffness; not a fully implicit incompressible augmented MPM implementation','Ice adds a phase-activated stiff XPBD bond network; its strain-fracture threshold is regularized, not toughness-calibrated','An explicitly budgeted external bending heat sink accelerates cooling','No old rejected material mesh was loaded']};(out/'report.json').write_text(json.dumps(report,indent=2));print('THERMAL_MPM',kind,report['seconds'],flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--kind',choices=['ice','lava'],required=True);ap.add_argument('--frames',type=int,default=62);ap.add_argument('--particles',type=int,default=4000);ap.add_argument('--substeps',type=int,default=12);a=ap.parse_args();simulate(a.kind,a.frames,a.particles,a.substeps)
