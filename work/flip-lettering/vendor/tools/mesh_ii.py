"""FLIP II offline reconstruction, diffuse whitewater and photon caustics.

The input is the NEW primary particle cache from src/flip.js. No procedural wave
surface, image interpolation or reused footage is involved. PCA kernels follow
the anisotropic-reconstruction idea, with explicit regularization and an exact
signed-triangle-volume root solve. This is not an implementation of every detail
of Yu & Turk. Volume matching is a reconstruction constraint, NOT a claim that
Lagrangian particle retention proves perfect physical incompressibility.
"""
from pathlib import Path
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import sys,json,time,gzip,struct,hashlib
import numpy as np
from numba import njit
from scipy.ndimage import gaussian_filter,map_coordinates
from scipy.spatial import cKDTree
from skimage.measure import marching_cubes
from mesh_cache import deposit,smooth_mesh,sample
ROOT=Path(__file__).resolve().parents[1]

@njit(cache=True)
def splat_anisotropic(p,G,bounds,shape,spacing):
    f=np.zeros(shape,np.float32)
    for n in range(len(p)):
        x,y,z=p[n];b=bounds[n]
        ia=max(0,int((x-b[0])/spacing));ib=min(shape[0]-1,int((x+b[0])/spacing)+1)
        ja=max(0,int((y-b[1])/spacing));jb=min(shape[1]-1,int((y+b[1])/spacing)+1)
        ka=max(0,int((z-b[2])/spacing));kb=min(shape[2]-1,int((z+b[2])/spacing)+1)
        a,c,d,e,g,j=G[n]
        for i in range(ia,ib+1):
            dx=i*spacing-x
            for iy in range(ja,jb+1):
                dy=iy*spacing-y
                for iz in range(ka,kb+1):
                    dz=iz*spacing-z
                    r=dx*dx*a+dy*dy*c+dz*dz*d+2*(dx*dy*e+dx*dz*g+dy*dz*j)
                    if r<1:
                        f[i,iy,iz]+=(1-r)**3
    return f

@njit(cache=True)
def signed_volume(v,faces):
    total=0.
    for a,b,c in faces:
        total+=v[a,0]*(v[b,1]*v[c,2]-v[b,2]*v[c,1])+v[a,1]*(v[b,2]*v[c,0]-v[b,0]*v[c,2])+v[a,2]*(v[b,0]*v[c,1]-v[b,1]*v[c,0])
    return total/6

def reconstruct(p,v,h,spacing,shape,extent,previous_iso=None):
    rho,vx,vy,vz=deposit(p,v,shape,spacing,h*.98)
    density=sample(rho,p,spacing)
    boundary=np.flatnonzero(density<3.55)
    radius=h*.99
    G=np.zeros((len(p),6),np.float32);G[:,:3]=1/radius**2
    bounds=np.full((len(p),3),radius,np.float32);centers=p.copy()
    if len(boundary):
        tree=cKDTree(p)
        # Batches bound temporary memory even for million-particle inputs.
        for start in range(0,len(boundary),24000):
            ids=boundary[start:start+24000]
            dist,nb=tree.query(p[ids],k=min(32,len(p)),workers=1)
            if dist.ndim==1:continue
            valid=dist<h*1.7
            weight=np.maximum(0,1-(dist/(h*1.7))**3)*valid
            total=np.maximum(weight.sum(axis=1),1e-8)
            points=p[nb]
            mean=np.einsum('nk,nkj->nj',weight,points)/total[:,None]
            delta=points-mean[:,None,:]
            cov=np.einsum('nk,nki,nkj->nij',weight,delta,delta)/total[:,None,None]
            eig,Q=np.linalg.eigh(cov)
            std=np.sqrt(np.maximum(eig,(h*.10)**2))
            std=np.maximum(std,std[:,-1,None]/2.7)
            axes=std/np.maximum(np.prod(std,axis=1)**(1/3),1e-8)[:,None]
            # Small isolated neighbourhoods cannot support trustworthy PCA axes.
            isolated=valid.sum(axis=1)<10
            axes[isolated]=1
            inv=1/(radius*axes)**2
            matrix=np.einsum('nik,nk,njk->nij',Q,inv,Q)
            G[ids]=matrix[:,[0,1,2,0,0,1],[0,1,2,1,2,2]]
            bounds[ids]=np.sqrt(np.einsum('nik,nk->ni',Q*Q,(radius*axes)**2))
            blend=np.where(isolated,0.,.12)[:,None]
            centers[ids]=p[ids]*(1-blend)+mean*blend
    field=splat_anisotropic(centers,G,bounds,shape,spacing)
    field=gaussian_filter(field,.34,mode='constant').astype(np.float32)
    # Keep boundaries closed: hard zero on the outermost sampling layer.
    for axis in range(3):
        sl=[slice(None)]*3;sl[axis]=0;field[tuple(sl)]=0
        sl[axis]=-1;field[tuple(sl)]=0
    particle_density=sample(field,p,spacing)
    isolated=particle_density<1.38
    drops=p[isolated]
    target=(len(p)-len(drops))*(h*.5)**3
    target=max(target,1e-12)
    low=.12;high=min(3.3,float(field.max())*.96)
    iso=np.clip(previous_iso if previous_iso else 1.80,low,high)
    history=[];best=None;lo_error=None;hi_error=None
    for it in range(9):
        verts,faces,_,_=marching_cubes(field,level=iso,spacing=(spacing,)*3,gradient_direction='ascent',allow_degenerate=False)
        verts=verts.astype(np.float32);faces=faces.astype(np.int32)
        vol=abs(signed_volume(verts,faces));error=(vol-target)/target
        history.append({'iso':float(iso),'volume':float(vol),'error':float(error)})
        if best is None or abs(error)<best[0]:best=(abs(error),verts,faces,float(iso),float(vol))
        if abs(error)<.0015:break
        if vol>target:low=iso;lo_error=vol-target
        else:high=iso;hi_error=vol-target
        # A derivative estimate from the shell of the scalar field accelerates
        # the volume root, with bisection as the safe bracketed fallback.
        eps=.13
        derivative=-np.sum(np.abs(field-iso)<eps)*spacing**3/(2*eps)
        candidate=iso-(vol-target)/min(derivative,-1e-12)
        if lo_error is not None and hi_error is not None:
            candidate=(low*hi_error-high*lo_error)/(hi_error-lo_error)
        iso=candidate if low+1e-5<candidate<high-1e-5 else (low+high)/2
    _,verts,faces,iso,volume=best
    verts,normals=smooth_mesh(verts,faces,2)
    if signed_volume(verts,faces)<0:
        faces=faces[:,[0,2,1]];normals*=-1
    vol=abs(signed_volume(verts,faces))
    stats={'kernel':'regularized local PCA / determinant-normalized ellipsoids',
           'anisotropicParticles':len(boundary),'isovalue':float(iso),
           'targetMeshVolume':target,'signedMeshVolume':vol,
           'meshVolumeRelativeError':(vol-target)/target,
           'nominalParticleVolume':len(p)*(h*.5)**3,
           'primaryDropletVolume':len(drops)*(h*.5)**3,
           'rootIterations':len(history),'volumeRoot':history}
    return field,(vx,vy,vz),verts,normals,faces,drops,iso,stats

class DiffuseWhitewater:
    """Persistent one-way subgrid air/liquid markers with hysteretic phases.

    Births are dt-scaled from resolved acceleration and outward flow. Spray has
    gravity plus exponential drag, bubbles have buoyancy and liquid drag, foam
    uses midpoint flow advection and two surface-projection iterations. No air
    pressure/volume is solved; secondary mass is not deducted from primary water.
    """
    def __init__(self,seed):
        self.rng=np.random.default_rng(seed)
        self.p=np.empty((0,3),np.float32);self.v=self.p.copy()
        self.radius=np.empty(0,np.float32);self.life=np.empty(0,np.float32)
        self.life0=np.empty(0,np.float32);self.age=np.empty(0,np.float32)
        self.mode=np.empty(0,np.int32);self.previous=None
        self.total_births=0;self.total_deaths=0;self.transitions=0
    def step(self,p,v,field,vel,spacing,h,dt,iso,extent,obstacles,enabled=True):
        grad=np.gradient(field,spacing)
        if len(self.p):
            den=sample(field,self.p,spacing)
            old=self.mode.copy()
            self.mode[den<iso*.42]=1
            self.mode[den>iso*1.65]=2
            surface=(den>iso*.72)&(den<iso*1.35)
            self.mode[surface]=0
            self.transitions+=int(np.count_nonzero(self.mode!=old))
            flow=np.column_stack([sample(a,self.p,spacing) for a in vel])
            spray=self.mode==1;bubbles=self.mode==2;foam=self.mode==0
            self.v[spray,1]-=9.81*dt
            self.v[spray]*=np.exp(-.22*dt)
            if np.any(bubbles):
                relaxation=1-np.exp(-dt/.065)
                self.v[bubbles]+=(flow[bubbles]-self.v[bubbles])*relaxation
                # Radius-dependent terminal rise speed, bounded for coarse markers.
                terminal=np.minimum(.45,np.sqrt(2*9.81*self.radius[bubbles]/.44))
                self.v[bubbles,1]+=terminal*relaxation
            if np.any(foam):
                mid=self.p[foam]+.5*dt*flow[foam]
                self.v[foam]=np.column_stack([sample(a,mid,spacing) for a in vel])
            self.p+=self.v*dt
            if np.any(foam):
                for _ in range(2):
                    pp=self.p[foam]
                    value=sample(field,pp,spacing)
                    g=np.column_stack([sample(a,pp,spacing) for a in grad])
                    shift=(value-iso)[:,None]*g/np.maximum(np.sum(g*g,axis=1)[:,None],1e-7)
                    length=np.linalg.norm(shift,axis=1)
                    shift*=np.minimum(1,h*.32/np.maximum(length,1e-9))[:,None]
                    self.p[foam]-=shift
            self.life-=dt;self.age+=dt
            keep=(self.life>0)&np.all(self.p>h*.90,axis=1)&np.all(self.p<extent-h*.90,axis=1)
            for o in obstacles:
                center=np.array(o['center'])
                if o['kind']=='box':keep&=~np.all(np.abs(self.p-center)<np.array(o['half'])+self.radius[:,None],axis=1)
                if o['kind']=='sphere':keep&=np.linalg.norm(self.p-center,axis=1)>o['radius']+self.radius
            self.total_deaths+=int(np.count_nonzero(~keep))
            for a in ['p','v','radius','life','life0','age','mode']:setattr(self,a,getattr(self,a)[keep])
        # Whitewater is suppressed in the zero-gravity capillary and viscous studies.
        if enabled and len(p) and len(self.p)<48000:
            ids=self.rng.choice(len(p),min(9000,len(p)),replace=False)
            pp=p[ids];vv=v[ids]
            den=sample(field,pp,spacing);g=np.column_stack([sample(a,pp,spacing) for a in grad])
            gn=np.linalg.norm(g,axis=1);normal=-g/np.maximum(gn[:,None],1e-7)
            speed=np.linalg.norm(vv,axis=1);outward=np.einsum('ij,ij->i',normal,vv)
            accel=np.zeros_like(vv)
            if self.previous is not None:
                valid=ids<len(self.previous);accel[valid]=(vv[valid]-self.previous[ids[valid]])/dt
            # Remove body gravity before measuring collision-induced acceleration.
            accel[:,1]+=9.81
            compression=np.maximum(0,-np.einsum('ij,ij->i',accel,normal)-3.)
            agitation=np.linalg.norm(accel,axis=1)
            energy=np.clip((speed**2-1.3)/12,0,1)
            potential=energy*(.55*np.clip(compression/18,0,1)+.35*np.clip((outward-.4)/2,0,1)+.10*np.clip((agitation-10)/40,0,1))
            eligible=(den>iso*.55)&(den<iso*1.9)&(gn>1/max(h,.0001))&(pp[:,1]>h*1.8)
            rate=potential*eligible*dt*12
            born=self.rng.random(len(ids))<np.minimum(.95,rate)
            selected=np.flatnonzero(born)
            if len(selected)>48000-len(self.p):selected=selected[:48000-len(self.p)]
            count=len(selected)
            if count:
                n=normal[selected];base=pp[selected];velocity=vv[selected]
                draw=self.rng.random(count)
                mode=np.where(draw<.42,2,np.where(draw<.84,0,1)).astype(np.int32)
                displacement=np.where(mode==2,-.42,np.where(mode==1,.28,.04))*h
                pos=base+n*displacement[:,None]
                velocity=velocity+n*np.where(mode==1,.30,0)[:,None]
                life=np.where(mode==0,self.rng.uniform(2.2,4.8,count),self.rng.uniform(.75,2.2,count)).astype(np.float32)
                radius=np.exp(self.rng.uniform(np.log(h*.030),np.log(h*.14),count)).astype(np.float32)
                for a,b in [('p',pos),('v',velocity),('mode',mode),('life',life),('life0',life.copy()),('radius',radius),('age',np.zeros(count,np.float32))]:
                    setattr(self,a,np.concatenate([getattr(self,a),b]))
                self.total_births+=count
        self.previous=v.copy()
        if not len(self.p):return np.empty((0,6),np.float32)
        fade=np.minimum(1,self.life/.25)*np.minimum(1,(self.age+dt)/.10)
        return np.column_stack([self.p,self.radius,self.mode,fade]).astype(np.float32)

@njit(cache=True)
def photon_splat(vertices,normals,faces,extent,floor_y,width,height):
    flux=np.zeros((height,width),np.float32)
    # Collimated key light used by the scene. One refracting water interface.
    I=np.array([.20,-.94,-.28],np.float64);I/=np.sqrt(np.sum(I*I))
    eta=1/1.333
    cell_area=extent[0]*extent[2]/(width*height)
    incoming=0.;deposited=0.
    for a,b,c in faces:
        p=(vertices[a]+vertices[b]+vertices[c])/3
        n=normals[a]+normals[b]+normals[c];nl=np.sqrt(np.sum(n*n))
        if nl<1e-8:continue
        n=n/nl
        # Back surfaces do not emit a second duplicate set of photons.
        if n[1]<.10 or p[1]<floor_y+.004:continue
        cosine=-np.sum(n*I)
        if cosine<=.05:continue
        cross=np.cross(vertices[b]-vertices[a],vertices[c]-vertices[a]);area=.5*np.sqrt(np.sum(cross*cross))
        d=eta*I+(eta*cosine-np.sqrt(max(0.,1-eta*eta*(1-cosine*cosine))))*n
        if d[1]>=-.05:continue
        t=(floor_y-p[1])/d[1]
        if t<=0:continue
        x=(p[0]+d[0]*t)/extent[0]*width-.5;z=(p[2]+d[2]*t)/extent[2]*height-.5
        value=area*cosine*(1-(.02037+.97963*(1-cosine)**5))
        incoming+=value
        ix=int(np.floor(x));iz=int(np.floor(z));fx=x-ix;fz=z-iz
        if ix<0 or iz<0 or ix>=width-1 or iz>=height-1:continue
        value=value/cell_area
        flux[iz,ix]+=value*(1-fx)*(1-fz);flux[iz,ix+1]+=value*fx*(1-fz)
        flux[iz+1,ix]+=value*(1-fx)*fz;flux[iz+1,ix+1]+=value*fx*fz
        deposited+=value*cell_area
    return flux,incoming,deposited

def caustics(verts,normals,faces,field,iso,extent,h):
    w,hg=384,256
    flux,incoming,deposited=photon_splat(verts,normals,faces,extent,h*1.04,w,hg)
    flux=gaussian_filter(flux,1.2)
    # Coverage comes from liquid geometry, not from an animated caustic texture.
    occupied=np.any(field>iso,axis=1)
    xx,zz=np.meshgrid(np.linspace(0,occupied.shape[0]-1,w),np.linspace(0,occupied.shape[1]-1,hg))
    coverage=map_coordinates(occupied.astype(np.float32),[xx,zz],order=1,mode='nearest')
    rgb=np.zeros((hg,w,2),np.uint8)
    rgb[:,:,0]=np.rint(np.clip(np.sqrt(np.maximum(flux,0))/4,0,1)*255).astype(np.uint8)
    rgb[:,:,1]=np.rint(coverage*255).astype(np.uint8)
    return rgb,{'incidentFlux':incoming,'depositedFlux':deposited,'method':'single-interface collimated photon splats','width':w,'height':hg}

def encode(path,verts,normals,faces,drops,white,diagnostic,extent,foam,caustic):
    def p16(a):return np.rint(np.clip(a/extent,0,1)*65535).astype('<u2').tobytes()
    h,w,_=caustic.shape
    body=struct.pack('<8I',0x43465233,len(verts),len(faces),len(drops),len(white),len(diagnostic),w,h)
    body+=p16(verts)+np.rint(np.clip(normals,-1,1)*32767).astype('<i2').tobytes()
    body+=np.rint(np.clip(foam,0,1)*255).astype('u1').tobytes()+faces.astype('<u4').tobytes()+p16(drops)
    body+=np.asarray(white,dtype='<f4').tobytes()+p16(diagnostic)+caustic.tobytes()
    with gzip.open(path,'wb',compresslevel=3) as f:f.write(body)
    return hashlib.sha256(body).hexdigest()

def main(name):
    folder=ROOT/'cache'/name;manifest=json.loads((folder/'manifest.json').read_text())
    config=manifest['config'];h=config['h'];spacing=h*.45
    extent=np.array(config['extent'],np.float32);shape=tuple(np.ceil(extent/spacing).astype(int)+1)
    ww=DiffuseWhitewater(config['seed']+501);stats=[];started=time.time();previous_iso=None
    for info in manifest['frames']:
        f=info['frame'];n=info['particles']
        raw=np.fromfile(folder/f'{f:04d}.particles',dtype='<f4');p=raw[:n*3].reshape(-1,3);v=raw[n*3:].reshape(-1,3)
        field,vel,verts,normals,faces,drops,iso,measure=reconstruct(p,v,h,spacing,shape,extent,previous_iso)
        previous_iso=iso
        white=ww.step(p,v,field,vel,spacing,h,manifest['frameDt'],iso,extent,info.get('colliders',config['obstacles']),name not in ['viscous','capillary'])
        foam=np.zeros(len(verts),np.float32)
        if len(white):
            fp=white[white[:,4]==0]
            if len(fp):
                dist,ids=cKDTree(fp[:,:3]).query(verts,k=min(8,len(fp)),workers=1)
                if dist.ndim==1:dist=dist[:,None];ids=ids[:,None]
                kernel=np.maximum(0,1-dist/(h*.92))**3
                foam=1-np.exp(-np.sum(kernel*fp[ids,5],axis=1)*.75)
        diagnostic=p[np.linspace(0,len(p)-1,min(22000,len(p))).astype(int)]
        caustic,photon_stats=caustics(verts,normals,faces,field,iso,extent,h)
        path=folder/f'{f:04d}.mesh.gz'
        digest=encode(path,verts,normals,faces,drops,white,diagnostic,extent,foam,caustic)
        m={'frame':f,'vertices':len(verts),'triangles':len(faces),'primaryDroplets':len(drops),'secondaryParticles':len(white),
           'foam':int(np.sum(white[:,4]==0)),'spray':int(np.sum(white[:,4]==1)),'bubbles':int(np.sum(white[:,4]==2)),
           'bytes':path.stat().st_size,'payloadSha256':digest,'caustics':photon_stats,**measure}
        stats.append(m)
        if f%12==0:print(name,'frame',f,'tris',len(faces),'volume error',round(measure['meshVolumeRelativeError']*100,3),'white',len(white),'elapsed',round(time.time()-started,1),flush=True)
    manifest['meshes']=stats;manifest['surface']={'method':'regularized anisotropic PCA kernels + bracketed volume root + Taubin smoothing',
        'spacing':spacing,'shape':[int(a) for a in shape],'volumeTolerance':.0025}
    manifest['whitewater']={'method':'dt-scaled entrainment potentials / hysteretic phases / persistent midpoint-advection / Newton surface projection',
        'births':ww.total_births,'deaths':ww.total_deaths,'transitions':ww.transitions,'twoWayCoupling':False}
    manifest['meshWallSeconds']=time.time()-started
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('MESH COMPLETE',name,manifest['meshWallSeconds'],flush=True)

if __name__=='__main__':
    for name in sys.argv[1:] or ['impact']:main(name)
