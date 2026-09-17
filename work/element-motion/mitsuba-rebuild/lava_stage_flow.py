"""CPU finite-volume viscous flow and a separate MAC buoyant plume.

The liquid solve conserves depth-integrated volume and transports thermal
energy. Crust meshes follow it one-way; this is not a fracture/contact solve.
The plume transports heat and moisture; condensate is a diagnostic optical
field, without latent-heat feedback or volcanic gas chemistry.
"""
from pathlib import Path
import os,json,time,argparse
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import numpy as np
from scipy.ndimage import map_coordinates,gaussian_filter
from scipy.fft import dctn,idctn
from scipy.sparse import coo_matrix,diags
from scipy.sparse.linalg import cg
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree
from lava_skin import normals
from lava_lobes_cpu import boundary
R=Path(__file__).resolve().parent/'lava-focus';O=R/'stages/motion';O.mkdir(exist_ok=True)

def sample(field,p,origin,dx):
    return map_coordinates(field,((p[:,:2]-origin)/dx-.5).T,order=1,mode='nearest')

class Flow:
    def __init__(self):
        self.dx=.025;self.origin=np.array([-1.2,-.8]);self.shape=(96,64)
        self.xy=self.origin+(np.moveaxis(np.indices(self.shape),0,-1)+.5)*self.dx
        a=np.load(R/'stages/magma.npz');v=a['v'];ij=np.floor((v[:,:2]-self.origin)/self.dx).astype(int)
        self.h=np.zeros(self.shape)
        valid=(ij>=0).all(1)&(ij<self.shape).all(1)
        np.maximum.at(self.h,(ij[valid,0],ij[valid,1]),v[valid,2])
        self.h=gaussian_filter(self.h,.7);self.h0=self.h.copy()
        self.energy=self.h*(1410+30*np.exp(-((self.xy[:,:,0]+.6)/.4)**2))
        self.mass0=self.h.sum()*self.dx**2;self.added=0.;self.heat_lost=0.;self.energy0=self.energy.sum();self.energy_added=0.
        self.u=np.zeros(self.shape);self.v=np.zeros(self.shape)
    def step(self,dt,t):
        h=self.h;temp=np.divide(self.energy,h,out=np.full_like(h,1410),where=h>1e-8)
        eta=6500*np.exp(np.clip(18000*(1/np.maximum(temp,900)-1/1450),-2,10))
        nu=eta/2700;yield_stress=70+700*np.clip((1380-temp)/220,0,1)
        sx=np.diff(h,axis=0)/self.dx-.13;sy=np.diff(h,axis=1)/self.dx
        hx=(h[1:]+h[:-1])/2;hy=(h[:,1:]+h[:,:-1])/2
        tx=2700*9.81*hx*np.abs(sx);ty=2700*9.81*hy*np.abs(sy)
        bx=np.clip(1-(yield_stress[1:]+yield_stress[:-1])/2/np.maximum(tx,1e-9),0,1)**2
        by=np.clip(1-(yield_stress[:,1:]+yield_stress[:,:-1])/2/np.maximum(ty,1e-9),0,1)**2
        kx=9.81*hx**3/(3*(nu[1:]+nu[:-1])/2)*bx
        ky=9.81*hy**3/(3*(nu[:,1:]+nu[:,:-1])/2)*by
        # Backward Euler diffusion with lagged positive mobility. Explicit
        # height diffusion was unstable despite its volume/positivity limiter.
        mx=kx*dt/self.dx**2;my=ky*dt/self.dx**2;nx,ny=self.shape
        diag=1+np.pad(mx,((1,0),(0,0)))+np.pad(mx,((0,1),(0,0)))+np.pad(my,((0,0),(1,0)))+np.pad(my,((0,0),(0,1)))
        oy=np.zeros(nx*ny-1);idx=(np.arange(nx)[:,None]*ny+np.arange(ny-1)[None,:]).ravel();oy[idx]=-my.ravel()
        matrix=diags([-mx.ravel(),oy,diag.ravel(),oy,-mx.ravel()],[-ny,-1,0,1,ny],format='csr')
        rhs=h+dt/self.dx*np.diff(np.pad(-.13*kx,((1,1),(0,0))),axis=0)
        height,info=cg(matrix,rhs.ravel(),x0=h.ravel(),rtol=1e-9,atol=0,maxiter=160);assert info==0,'Implicit flow solve did not converge'
        height=height.reshape(self.shape)
        qx=-kx*(np.diff(height,axis=0)/self.dx-.13)
        qy=-ky*np.diff(height,axis=1)/self.dx
        # A donor can spend at most one quarter of its volume per face.
        qx=np.clip(qx,-h[1:]*self.dx/(4*dt),h[:-1]*self.dx/(4*dt))
        qy=np.clip(qy,-h[:,1:]*self.dx/(4*dt),h[:,:-1]*self.dx/(4*dt))
        fx=np.pad(qx,((1,1),(0,0)));fy=np.pad(qy,((0,0),(1,1)))
        ex=np.pad(qx*np.where(qx>=0,temp[:-1],temp[1:]),((1,1),(0,0)))
        ey=np.pad(qy*np.where(qy>=0,temp[:,:-1],temp[:,1:]),((0,0),(1,1)))
        self.h=h-dt/self.dx*(np.diff(fx,axis=0)+np.diff(fy,axis=1))
        self.energy-=dt/self.dx*(np.diff(ex,axis=0)+np.diff(ey,axis=1))
        feed=np.exp(-((self.xy[:,:,0]+.71)/.12)**2-(self.xy[:,:,1]/.13)**2)
        rate=.0018*max(0,1-t/8);add=feed/feed.sum()*rate/self.dx**2*dt
        self.h+=add;self.energy+=add*1450;self.added+=rate*dt;self.energy_added+=float(add.sum()*1450)
        temp=np.divide(self.energy,self.h,out=np.full_like(h,293.15),where=self.h>1e-8)
        # Natural radiative and convective loss from the actual top area.
        loss=(.94*5.670374419e-8*(temp**4-293.15**4)+35*(temp-293.15))/(2700*1200)*dt
        loss=np.minimum(loss,np.maximum(0,self.energy-self.h*293.15));loss[self.h<1e-7]=0
        self.energy-=loss;self.heat_lost+=float(loss.sum())
        self.u=(fx[1:]+fx[:-1])/(2*np.maximum(self.h,.003));self.v=(fy[:,1:]+fy[:,:-1])/(2*np.maximum(self.h,.003))
        assert self.h.min()>-1e-10 and np.isfinite(self.energy).all()
        return temp

class Plume:
    def __init__(self):
        self.shape=(48,32,48);self.dx=.05;self.origin=np.array([-1.2,-.8,0.]);self.extent=np.array(self.shape)*self.dx
        self.center=np.indices(self.shape).astype('f4')+.5
        self.world=np.moveaxis(self.center,0,-1)*self.dx+self.origin
        self.vel=[np.zeros(tuple(n+(axis==i) for i,n in enumerate(self.shape))) for axis in range(3)]
        self.coords=[np.indices(v.shape).astype('f4')+np.array([0 if i==axis else .5 for i in range(3)])[:,None,None,None] for axis,v in enumerate(self.vel)]
        self.heat=np.zeros(self.shape);self.moisture=np.zeros(self.shape);self.projection=[]
        rng=np.random.default_rng(847)
        for v in self.vel:v[:]=gaussian_filter(rng.normal(0,.13,v.shape),1.1)
        freqs=[2*(np.cos(np.pi*np.arange(n)/n)-1)/self.dx**2 for n in self.shape]
        self.eigen=freqs[0][:,None,None]+freqs[1][None,:,None]+freqs[2][None,None,:];self.eigen[0,0,0]=1
        z=self.world[:,:,:,2];self.sponge=np.exp(-np.maximum(z-1.9,0)*4)
    def centered(self):return [(np.take(v,range(v.shape[i]-1),axis=i)+np.take(v,range(1,v.shape[i]),axis=i))/2 for i,v in enumerate(self.vel)]
    def advect(self,field,coord,dt,centers):
        velocity=np.array([map_coordinates(c,coord-.5,order=1,mode='nearest') for c in centers])
        return map_coordinates(field,coord-velocity*dt/self.dx-.5,order=1,mode='constant',cval=0)
    def step(self,dt,flow,temp):
        centers=self.centered();new=[]
        for axis,field in enumerate(self.vel):
            coord=self.coords[axis];vel=np.array([map_coordinates(c,coord-.5,order=1,mode='nearest') for c in centers])
            origin=np.array([0 if i==axis else .5 for i in range(3)])[:,None,None,None]
            new.append(map_coordinates(field,coord-vel*dt/self.dx-origin,order=1,mode='constant',cval=0))
        self.heat=self.advect(self.heat,self.center,dt,centers)
        self.moisture=self.advect(self.moisture,self.center,dt,centers)
        self.vel=new
        # Restore vortical detail lost to semi-Lagrangian transport.
        c=self.centered();grad=[np.gradient(q,self.dx) for q in c]
        curl=np.array([grad[2][1]-grad[1][2],grad[0][2]-grad[2][0],grad[1][0]-grad[0][1]])
        magnitude=np.sqrt((curl*curl).sum(0));direction=np.array(np.gradient(magnitude,self.dx));direction/=np.maximum(np.sqrt((direction*direction).sum(0)),1e-8)
        force=np.moveaxis(np.cross(np.moveaxis(direction,0,-1),np.moveaxis(curl,0,-1)), -1,0)*.7*self.dx
        for axis,v in enumerate(self.vel):
            sl=[slice(None)]*3;sl[axis]=slice(1,-1);v[tuple(sl)]+=dt*(np.take(force[axis],range(self.shape[axis]-1),axis=axis)+np.take(force[axis],range(1,self.shape[axis]),axis=axis))/2
        xy=self.world[:,:,0,:2].reshape(-1,2);surface=sample(flow.h,xy,flow.origin,flow.dx).reshape(self.shape[:2])
        hot=sample(temp,xy,flow.origin,flow.dx).reshape(self.shape[:2]);src=np.exp(-((self.world[:,:,:,2]-surface[:,:,None]-.035)/.048)**2)
        src*=((surface>.04)*np.clip((hot-1180)/260,0,1))[:,:,None]
        # Fixed-source hot moist gas is diluted and cooled by transport.
        mix=1-np.exp(-src*dt*2.5)
        self.heat+=(80-self.heat)*mix;self.moisture+=(.18-self.moisture)*mix
        self.heat=gaussian_filter(self.heat,.38)*self.sponge
        self.moisture=gaussian_filter(self.moisture,.38)*self.sponge
        self.vel[2][:,:,1:-1]+=dt*.025*(self.heat[:,:,1:]+self.heat[:,:,:-1])/2
        self.vel[0]+=dt*.025
        # No-through-flow MAC boundaries. Absorbing top layer keeps the
        # short visible study clear of the closed-domain boundary.
        for axis,v in enumerate(self.vel):
            sl=[slice(None)]*3;sl[axis]=0;v[tuple(sl)]=0;sl[axis]=-1;v[tuple(sl)]=0
        divergence=sum(np.diff(v,axis=i)/self.dx for i,v in enumerate(self.vel))
        rhs=divergence/dt;rhs-=rhs.mean();pressure=idctn(dctn(rhs,type=2,norm='ortho')/self.eigen,type=2,norm='ortho')
        for i,v in enumerate(self.vel):
            sl=[slice(None)]*3;sl[i]=slice(1,-1);v[tuple(sl)]-=dt*np.diff(pressure,axis=i)/self.dx
        after=sum(np.diff(v,axis=i)/self.dx for i,v in enumerate(self.vel))
        self.projection.append((float(np.sqrt(np.mean(divergence**2))),float(np.sqrt(np.mean(after**2)))))
        saturation=.017*np.exp(.035*np.clip(self.heat,0,90))
        self.density=np.maximum(0,self.moisture-saturation)*90
        # Lava occupies cells beneath the surface; do not render fog inside it.
        self.density*=self.world[:,:,:,2]>surface[:,:,None]+.012
        assert np.isfinite(self.density).all() and self.density.max()<100

def simplify(a):
    v=a['v'];f=a['f'];e=np.r_[f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]
    adj=coo_matrix((np.ones(len(e),'u1'),(e[:,0],e[:,1])),shape=(len(v),len(v))).tocsr();_,label=connected_components(adj,directed=False)
    key=np.c_[np.round(v/.004).astype('i4'),label]
    _,inverse=np.unique(key,axis=0,return_inverse=True);count=np.bincount(inverse)
    b={}
    for k in ['v','rest','uv','temperature','component']:
        x=a[k]
        b[k]=np.array([np.bincount(inverse,weights=c)/count for c in x.T]).T if x.ndim==2 else np.bincount(inverse,weights=x)/count
    ff=inverse[f];ff=ff[(ff[:,0]!=ff[:,1])&(ff[:,1]!=ff[:,2])&(ff[:,0]!=ff[:,2])]
    b['f']=ff.astype('i4');b['normal']=normals(b['v'],b['f'])
    for k in ['camera_eye','camera_target','camera_fov']:b[k]=a[k]
    b['camera_eye']=np.array([1.02,-3.0,1.50]);b['camera_target']=np.array([-.04,0,.48]);b['camera_fov']=np.array(39.)
    b['piece']=np.bincount(inverse,weights=label)/count
    return b

def liquid_mesh(flow,temp):
    # The rendered liquid comes directly from the finite-volume free surface.
    nx,ny=np.array(flow.shape)*2;ij=np.indices((nx,ny)).astype('f8')/2-.25
    hh=map_coordinates(flow.h,ij,order=1,mode='constant',cval=0)
    tt=map_coordinates(temp,ij,order=1,mode='nearest')
    xy=flow.origin+(np.moveaxis(ij,0,-1)+.5)*flow.dx
    v=np.c_[xy.reshape(-1,2),hh.ravel()];j=np.arange(nx-1)[:,None]*ny+np.arange(ny-1)[None,:]
    f=np.r_[np.c_[j.ravel(),(j+ny).ravel(),(j+ny+1).ravel()],np.c_[j.ravel(),(j+ny+1).ravel(),(j+1).ravel()]]
    f=f[(hh.ravel()[f]>.003).all(1)];ids,ix=np.unique(f,return_inverse=True);v=v[ids];f=ix.reshape(-1,3);n=len(v);edge=boundary(f)
    lower=v.copy();lower[:,2]=0
    sides=np.r_[np.c_[edge[:,0],edge[:,0]+n,edge[:,1]+n],np.c_[edge[:,0],edge[:,1]+n,edge[:,1]]]
    av=np.r_[v,lower];af=np.r_[f,f[:,[0,2,1]]+n,sides]
    return dict(v=av,f=af,rest=av.copy(),uv=av[:,:2]*4,temperature=np.r_[tt.ravel()[ids],np.full(n,950.)],component=np.zeros(n*2))

def main(frames,seconds):
    start=time.time();flow=Flow();plume=Plume();a=simplify(dict(np.load(R/'stages/cooling.npz')))
    initial=a['v'].copy();crust=a['component']>.5;pieces=np.unique(a['piece'][crust]).astype(int);centers=np.array([initial[a['piece']==p].mean(0) for p in pieces]);original=centers.copy();base_h=sample(flow.h,centers,flow.origin,flow.dx)
    snapshots=[];dt=.05;steps=round(seconds/dt);at=np.linspace(0,steps-1,frames).round().astype(int);history=[]
    for step in range(steps):
        t=step*dt
        for sub in range(5):
            temp=flow.step(dt/5,t+sub*dt/5);u=sample(flow.u,centers,flow.origin,flow.dx);v=sample(flow.v,centers,flow.origin,flow.dx);centers[:,:2]+=np.c_[u,v]*dt/5
        plume.step(dt,flow,temp)
        if step in at:
            frame=len(history);moved=initial.copy();delta=sample(flow.h,centers,flow.origin,flow.dx)-base_h
            for pi,piece in enumerate(pieces):
                mask=a['piece']==piece;shift=centers[pi]-original[pi];shift[2]=delta[pi];moved[mask]+=shift
            cf=a['f'][crust[a['f']].all(1)];ids,ix=np.unique(cf,return_inverse=True);cf=ix.reshape(-1,3)
            b=liquid_mesh(flow,temp);offset=len(b['v']);b['f']=np.r_[b['f'],cf+offset]
            for key in ['v','rest','uv','temperature','component']:
                part=moved[ids] if key=='v' else a[key][ids]
                if key=='temperature':part=np.maximum(940,part-t*1.8)
                b[key]=np.r_[b[key],part]
            b['normal']=normals(b['v'],b['f'])
            for key in ['camera_eye','camera_target','camera_fov']:b[key]=a[key]
            np.savez_compressed(O/f'mesh-{frame:03}.npz',**{k:q.astype('i4') if k=='f' else q.astype('f4') for k,q in b.items()})
            np.savez_compressed(O/f'plume-{frame:03}.npz',density=plume.density.astype('f4'),origin=plume.origin,extent=plume.extent)
            np.savez_compressed(O/f'field-{frame:03}.npz',height=flow.h.astype('f4'),temperature=temp.astype('f4'),u=flow.u.astype('f4'),v=flow.v.astype('f4'))
            d=plume.density;z=plume.world[:,:,:,2]
            history.append({'frame':frame,'seconds':round(t+dt,3),'volumeM3':float(flow.h.sum()*flow.dx**2),'densityMax':float(d.max()),'plumeCentroidZ':float((d*z).sum()/max(d.sum(),1e-9)),'maxVertexTravelM':float(np.linalg.norm(centers[:,:2]-original[:,:2],axis=1).max())})
    masserr=abs(flow.h.sum()*flow.dx**2-flow.mass0-flow.added)/flow.mass0
    heaterr=abs(flow.energy.sum()-flow.energy0-flow.energy_added+flow.heat_lost)/flow.energy0
    projection=np.array(plume.projection);assert masserr<1e-10 and heaterr<1e-10 and projection[:,1].max()<1e-8
    assert history[-1]['maxVertexTravelM']>.01 and history[-1]['densityMax']>.01
    report={'device':'CPU','seconds':round(time.time()-start,2),'frames':frames,'simulatedSeconds':seconds,'flowGrid':list(flow.shape),'plumeGrid':list(plume.shape),'flow':'Conservative finite-volume lubrication / Bingham yield approximation, temperature viscosity, donor-limited fluxes, gravity and source feed','thermal':'Conservative advection and natural top-surface radiation/convection; bulk depth average, with authored pre-existing crust temperatures','plume':'MAC pressure projection, semi-Lagrangian advection, buoyancy, heat and moisture; approximate equilibrium condensate opacity','relativeVolumeError':float(masserr),'relativeThermalLedgerError':float(heaterr),'maxPostProjectionDivergenceRMS':float(projection[:,1].max()),'maxPreProjectionDivergenceRMS':float(projection[:,0].max()),'history':history,'limits':['One-way mesh following of the height/velocity field, not a coupled 3D solid fracture/contact simulation','Crust deformation may intersect and has no collision solve','Plume condensation has no latent heat or chemical aerosol feedback','Plume has closed velocity boundaries and an absorbing upper layer','Full basalt cooling/crystallization and the separate obsidian branch are material stills, not simulated transformations']}
    (O/'simulation.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='history'}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--frames',type=int,default=32);p.add_argument('--seconds',type=float,default=12);a=p.parse_args();main(a.frames,a.seconds)
