"""3D quadratic MLS-MPM/APIC with constitutive projection on NVIDIA Warp.

Reference formulation: Hu et al. 2018 MLS-MPM and the 2019 MPM course.
This implements an independent reduced material model, not Houdini internals.
Sand: logarithmic Drucker-Prager projection. Snow: compression/tension limits
with plastic-volume hardening. Metal: deviatoric logarithmic yield projection.
The bending support is an explicit external force and is removed on release.
"""
import argparse, json, sys, time, hashlib
from pathlib import Path
import numpy as np
import warp as wp

R=Path(__file__).resolve().parent
sys.path.insert(0,str(R.parent))
from shared_motion import pose,turn_rate
wp.config.kernel_cache_dir=str(R/'warp-cache')
wp.init()

@wp.func
def weight(q:float, a:int):
    val=float(0.0)
    if a==0: val=0.5*(1.5-q)*(1.5-q)
    elif a==1: val=0.75-(q-1.0)*(q-1.0)
    else: val=0.5*(q-0.5)*(q-0.5)
    return val

@wp.kernel
def transfer(x:wp.array(dtype=wp.vec3),v:wp.array(dtype=wp.vec3),
             C:wp.array(dtype=wp.mat33),F:wp.array(dtype=wp.mat33),
             jp:wp.array(dtype=float),rest:wp.array(dtype=wp.vec3),
             birth:wp.array(dtype=float),clock:wp.array(dtype=float),turn:wp.array(dtype=float),
             gm:wp.array3d(dtype=float),gv:wp.array3d(dtype=wp.vec3),
             dx:float,dt:float,pvol:float,rho:float,mu0:float,la0:float,kind:int):
    p=wp.tid()
    t=clock[0]
    if t<birth[p]: return
    I=wp.identity(n=3,dtype=float)
    fp=(I+C[p]*dt)*F[p]
    U,s,V=wp.svd3(fp)
    s=wp.vec3(wp.clamp(s[0],0.4,2.0),wp.clamp(s[1],0.4,2.0),wp.clamp(s[2],0.4,2.0))
    mu=mu0
    la=la0
    oldJ=s[0]*s[1]*s[2]
    if kind==0:
        eps=wp.vec3(wp.log(s[0]),wp.log(s[1]),wp.log(s[2]))
        tr=eps[0]+eps[1]+eps[2]+jp[p]
        dev=eps-wp.vec3((eps[0]+eps[1]+eps[2])/3.0)
        norm=wp.length(dev)
        if tr>=0.0:
            s=wp.vec3(1.0)
            jp[p]=0.0
        else:
            delta=norm+(3.0*la+2.0*mu)/(2.0*mu)*tr*0.23
            if delta>0.0:
                eps=eps-dev*(delta/wp.max(norm,1.0e-6))
                s=wp.vec3(wp.exp(eps[0]),wp.exp(eps[1]),wp.exp(eps[2]))
            jp[p]=0.0
    elif kind==1:
        hard=wp.exp(wp.clamp(8.0*(1.0-jp[p]),-2.0,3.0))
        mu=mu0*hard
        la=la0*hard
        s=wp.vec3(wp.clamp(s[0],0.975,1.006),wp.clamp(s[1],0.975,1.006),wp.clamp(s[2],0.975,1.006))
        jp[p]=wp.clamp(jp[p]*oldJ/(s[0]*s[1]*s[2]),0.65,1.4)
    elif kind==2:
        eps=wp.vec3(wp.log(s[0]),wp.log(s[1]),wp.log(s[2]))
        tr=(eps[0]+eps[1]+eps[2])/3.0
        dev=eps-wp.vec3(tr)
        norm=wp.length(dev)
        lim=0.035+0.05*jp[p]
        if norm>lim:
            jp[p]=wp.min(1.0,jp[p]+(norm-lim)*0.4)
            eps=wp.vec3(tr)+dev*(lim/norm)
            s=wp.vec3(wp.exp(eps[0]),wp.exp(eps[1]),wp.exp(eps[2]))
    elif kind==3:
        # Cohesive yield-limited viscous solid for wet mud.
        eps=wp.vec3(wp.log(s[0]),wp.log(s[1]),wp.log(s[2]))
        tr=(eps[0]+eps[1]+eps[2])/3.0
        dev=eps-wp.vec3(tr)
        norm=wp.length(dev)
        if norm>0.018: dev=dev*(0.018/norm)
        eps=wp.vec3(tr)+dev
        s=wp.vec3(wp.exp(eps[0]),wp.exp(eps[1]),wp.exp(eps[2]))
    fp=U*wp.diag(s)*wp.transpose(V)
    F[p]=fp
    rot=U*wp.transpose(V)
    J=s[0]*s[1]*s[2]
    stress=2.0*mu*(fp-rot)*wp.transpose(fp)+I*(la*(J-1.0)*J)
    if kind==0:
        logs=wp.vec3(wp.log(s[0]),wp.log(s[1]),wp.log(s[2]))
        tr=logs[0]+logs[1]+logs[2]
        stress=U*wp.diag(logs*(2.0*mu)+wp.vec3(la*tr))*wp.transpose(U)
    mass=pvol*rho
    affine=stress*(-dt*pvol*4.0/(dx*dx))+C[p]*mass
    support=1.0-wp.smoothstep(2.0,2.55,t)
    age=t-birth[p]
    # Support offsets weight while allowing free tangential momentum. It must
    # never tether every particle back to its birth position (a rigid rope).
    drag=0.75
    if kind==0: drag=4.0
    if kind==1: drag=5.0
    force=-v[p]*drag
    force+=wp.vec3(0.0,0.0,9.81*support*wp.exp(-age*0.32))
    # Emitter momentum persists; no per-frame position projection to a curve.
    vv=v[p]+force*dt
    if kind==0 or kind==1:
        if t<1.68:
            ti=wp.min(int(t*120.0),turn.shape[0]-2);u=t*120.0-float(ti)
            omega=(turn[ti]*(1.0-u)+turn[ti+1]*u)*0.30*wp.exp(-age*4.0)
            angle=omega*dt;cosa=wp.cos(angle);sina=wp.sin(angle)
            vv=wp.vec3(vv[0]*cosa-vv[2]*sina,vv[1],vv[0]*sina+vv[2]*cosa)
    origin=wp.vec3(-6.0,-2.0,-2.0)
    local=(x[p]-origin)/dx
    base=wp.vec3i(int(wp.floor(local[0]-0.5)),int(wp.floor(local[1]-0.5)),int(wp.floor(local[2]-0.5)))
    fx=local-wp.vec3(float(base[0]),float(base[1]),float(base[2]))
    for i in range(3):
        for j in range(3):
            for k in range(3):
                a=base[0]+i;b=base[1]+j;c=base[2]+k
                if a>=0 and a<gm.shape[0] and b>=0 and b<gm.shape[1] and c>=0 and c<gm.shape[2]:
                    w=weight(fx[0],i)*weight(fx[1],j)*weight(fx[2],k)
                    dp=(wp.vec3(float(i),float(j),float(k))-fx)*dx
                    wp.atomic_add(gm,a,b,c,w*mass)
                    wp.atomic_add(gv,a,b,c,w*(vv*mass+affine*dp))

@wp.kernel
def grid(gm:wp.array3d(dtype=float),gv:wp.array3d(dtype=wp.vec3),dt:float,dx:float,kind:int):
    i,j,k=wp.tid()
    m=gm[i,j,k]
    if m>0.0:
        vv=gv[i,j,k]/m+wp.vec3(0.0,0.0,-9.81*dt)
        # Out-of-frame catch below the camera; no visible floor or panel.
        if k<3 and vv[2]<0.0: vv=wp.vec3(vv[0]*0.96,vv[1]*0.96,0.0)
        if i<3 and vv[0]<0.0: vv[0]=0.0
        if i>gm.shape[0]-4 and vv[0]>0.0: vv[0]=0.0
        if j<3 and vv[1]<0.0: vv[1]=0.0
        if j>gm.shape[1]-4 and vv[1]>0.0: vv[1]=0.0
        gv[i,j,k]=vv

@wp.kernel
def gather(x:wp.array(dtype=wp.vec3),v:wp.array(dtype=wp.vec3),C:wp.array(dtype=wp.mat33),birth:wp.array(dtype=float),clock:wp.array(dtype=float),gv:wp.array3d(dtype=wp.vec3),dx:float,dt:float):
    p=wp.tid()
    if clock[0]<birth[p]:return
    local=(x[p]-wp.vec3(-6.0,-2.0,-2.0))/dx
    base=wp.vec3i(int(wp.floor(local[0]-0.5)),int(wp.floor(local[1]-0.5)),int(wp.floor(local[2]-0.5)))
    fx=local-wp.vec3(float(base[0]),float(base[1]),float(base[2]))
    vv=wp.vec3(0.0);cc=wp.mat33(0.0)
    for i in range(3):
        for j in range(3):
            for k in range(3):
                a=base[0]+i;b=base[1]+j;c=base[2]+k
                if a>=0 and a<gv.shape[0] and b>=0 and b<gv.shape[1] and c>=0 and c<gv.shape[2]:
                    w=weight(fx[0],i)*weight(fx[1],j)*weight(fx[2],k)
                    vel=gv[a,b,c]
                    vv+=vel*w
                    dp=wp.vec3(float(i),float(j),float(k))-fx
                    cc+=wp.outer(vel,dp)*(4.0*w/dx)
    v[p]=vv
    C[p]=cc
    x[p]=x[p]+vv*dt

@wp.kernel
def tick(clock:wp.array(dtype=float),dt:float):clock[0]+=dt

def source(kind,n):
    rng=np.random.default_rng(719)
    birth=np.sort(rng.uniform(.08,1.68,n)).astype('f4')
    tgrid=np.linspace(.08,1.68,2001)
    pd=np.array([pose(float(t))[0] for t in tgrid]);dd=np.array([pose(float(t))[1] for t in tgrid])
    p=np.column_stack([np.interp(birth,tgrid,pd[:,0]),np.zeros(n),np.interp(birth,tgrid,pd[:,1])])
    d=np.column_stack([np.interp(birth,tgrid,dd[:,0]),np.zeros(n),np.interp(birth,tgrid,dd[:,1])])
    no=np.column_stack([-d[:,2],np.zeros(n),d[:,0]])
    if kind=='metal':
        across=rng.uniform(-.24,.24,n)
        p+=no*across[:,None];p[:,1]=rng.uniform(-.023,.023,n)+.035*np.sin(birth*12)*np.cos(across*8)
        volume=8.0*.48*.046
    else:
        a=rng.uniform(0,np.pi*2,n);radius=np.sqrt(rng.random(n))*(.075+.075*np.sin(birth*19)**4)
        p+=no*(radius*np.cos(a))[:,None];p[:,1]=radius*np.sin(a)
        volume=8.0*np.pi*.13**2
    velocity=d*(2.1+.55*np.sin(birth*16))[:,None]
    velocity+=no*(.35*np.sin(birth*27))[:,None]
    velocity[:,1]=.32*np.sin(birth*11)
    if kind=='sand':
        velocity+=no*(1.1*np.sin(birth*43)+.45*np.sin(birth*79))[:,None]
        velocity[:,1]+=.35*np.sin(birth*53)
    if kind in ['sand','snow']:
        velocity+=d*4.4
    return p.astype('f4'),velocity.astype('f4'),birth,volume/n

def run(kind,n,frames,substeps,dx):
    start=time.time();folder=R/'cache'/kind;folder.mkdir(parents=True,exist_ok=True)
    p,vel,birth,vol=source(kind,n);kid=['sand','snow','metal','mud'].index(kind)
    rho,E,nu={'sand':(1600,35000,.2),'snow':(380,24000,.2),'metal':(7800,800000,.3),'mud':(1500,22000,.35)}[kind]
    mu=E/(2*(1+nu));la=E*nu/((1+nu)*(1-2*nu));dt=1/(30*substeps)
    x=wp.array(p,dtype=wp.vec3);v=wp.array(vel,dtype=wp.vec3);rest=wp.array(p,dtype=wp.vec3);b=wp.array(birth,dtype=float)
    C=wp.zeros(n,dtype=wp.mat33);F=wp.array(np.tile(np.eye(3,dtype='f4'),(n,1,1)),dtype=wp.mat33)
    jp=wp.array(np.full(n,1 if kind=='snow' else 0,dtype='f4'),dtype=float)
    shape=tuple(int(z/dx) for z in [12,4,8]);gm=wp.zeros(shape,dtype=float);gv=wp.zeros(shape,dtype=wp.vec3);clock=wp.zeros(1,dtype=float)
    turn=wp.array(np.array([np.clip(turn_rate(t),-25,25) for t in np.arange(482)/120],dtype='f4'),dtype=float)
    args=[x,v,C,F,jp,rest,b,clock,turn,gm,gv,dx,dt,vol,rho,mu,la,kid]
    def step():
        gm.zero_();gv.zero_()
        wp.launch(transfer,n,args);wp.launch(grid,shape,[gm,gv,dt,dx,kid]);wp.launch(gather,n,[x,v,C,b,clock,gv,dx,dt]);wp.launch(tick,1,[clock,dt])
    wp.load_module(device='cuda:0')
    with wp.ScopedCapture() as capture:
        for _ in range(substeps):step()
    report=[];np.savez_compressed(folder/'static.npz',rest=p,birth=birth,volume=vol,kind=kind)
    for frame in range(frames):
        wp.capture_launch(capture.graph);wp.synchronize()
        pp=x.numpy();vv=v.numpy();tt=float(clock.numpy()[0]);active=birth<=tt
        assert np.isfinite(pp).all() and np.isfinite(vv).all(),('nonfinite',kind,frame)
        maxv=float(np.linalg.norm(vv[active],axis=1).max(initial=0));assert maxv<80,('unstable',kind,frame,maxv)
        np.savez_compressed(folder/f'{frame:04}.npz',p=pp.astype('f4'),v=vv.astype('f4'),F=F.numpy().astype('f2'),plastic=jp.numpy().astype('f2'),t=tt)
        report.append({'frame':frame,'active':int(active.sum()),'maxSpeed':round(maxv,4),'centroid':pp[active].mean(0).tolist() if active.any() else [0,0,0]})
        if frame%15==0:print(kind,frame,'speed',round(maxv,2),'seconds',round(time.time()-start,1),flush=True)
    result={'kind':kind,'particles':n,'frames':frames,'seconds':round(time.time()-start,2),'dx':dx,'substeps':substeps,'sourceHash':hashlib.sha256((R.parent/'shared-trail.json').read_bytes()).hexdigest(),'solver':'3D MLS-MPM/APIC','material':{'density':rho,'youngModulus':E,'poisson':nu},'limits':'Reduced constitutive model; artist-controlled suspension; no claim of Houdini equivalence','framesAudit':report}
    (folder/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('COMPLETE',kind,frames,round(time.time()-start,1),flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('kind',choices=['sand','snow','metal','mud']);a.add_argument('--particles',type=int,default=60000);a.add_argument('--frames',type=int,default=120);a.add_argument('--substeps',type=int,default=60);a.add_argument('--dx',type=float,default=.05);q=a.parse_args();run(q.kind,q.particles,q.frames,q.substeps,q.dx)
