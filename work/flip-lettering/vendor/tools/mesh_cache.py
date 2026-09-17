"""Reconstruct evolving surfaces and advect secondary particles from FLIP caches.
The primary solver is JavaScript (src/flip.js); this is an offline geometry pass.
No procedural wave displacement and no temporal interpolation of rendered images.
"""
from pathlib import Path
import sys,json,time,gzip,struct
import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates
from scipy.spatial import cKDTree
from skimage.measure import marching_cubes
from numba import njit
ROOT=Path(__file__).resolve().parents[1]

@njit(cache=True)
def deposit(p,v,shape,spacing,radius):
    rho=np.zeros(shape,np.float32)
    vx=np.zeros(shape,np.float32);vy=np.zeros(shape,np.float32);vz=np.zeros(shape,np.float32)
    R2=radius*radius
    for n in range(len(p)):
        x,y,z=p[n];vel=v[n]
        ia=max(0,int((x-radius)/spacing));ib=min(shape[0]-1,int((x+radius)/spacing)+1)
        ja=max(0,int((y-radius)/spacing));jb=min(shape[1]-1,int((y+radius)/spacing)+1)
        ka=max(0,int((z-radius)/spacing));kb=min(shape[2]-1,int((z+radius)/spacing)+1)
        for i in range(ia,ib+1):
            dx=i*spacing-x
            for j in range(ja,jb+1):
                dy=j*spacing-y
                for k in range(ka,kb+1):
                    dz=k*spacing-z;r2=(dx*dx+dy*dy+dz*dz)/R2
                    if r2<1:
                        w=(1-r2)**3;rho[i,j,k]+=w
                        vx[i,j,k]+=w*vel[0];vy[i,j,k]+=w*vel[1];vz[i,j,k]+=w*vel[2]
    for i in range(shape[0]):
        for j in range(shape[1]):
            for k in range(shape[2]):
                if rho[i,j,k]>1e-6:
                    inv=1/rho[i,j,k];vx[i,j,k]*=inv;vy[i,j,k]*=inv;vz[i,j,k]*=inv
    return rho,vx,vy,vz

@njit(cache=True)
def smooth_mesh(vertices,faces,iterations=2):
    # Non-shrinking Taubin smoothing. The physics particle positions are untouched.
    n=len(vertices);v=vertices.copy();s=np.zeros_like(v);count=np.zeros(n,np.int32)
    for a,b,c in faces:
        count[a]+=2;count[b]+=2;count[c]+=2
    for t in range(iterations*2):
        s[:]=0
        for a,b,c in faces:
            for d in range(3):
                s[a,d]+=v[b,d]+v[c,d];s[b,d]+=v[a,d]+v[c,d];s[c,d]+=v[a,d]+v[b,d]
        factor=.36 if t%2==0 else -.37
        for a in range(n):
            if count[a]:
                for d in range(3):v[a,d]+=factor*(s[a,d]/count[a]-v[a,d])
    normals=np.zeros_like(v)
    for a,b,c in faces:
        x1,y1,z1=v[b]-v[a];x2,y2,z2=v[c]-v[a]
        nx=y1*z2-z1*y2;ny=z1*x2-x1*z2;nz=x1*y2-y1*x2
        for k in (a,b,c):normals[k,0]+=nx;normals[k,1]+=ny;normals[k,2]+=nz
    for a in range(n):
        l=np.sqrt(np.sum(normals[a]*normals[a]))
        if l>1e-12:normals[a]/=l
    return v,normals

def sample(field,p,spacing):
    return map_coordinates(field,(p/spacing).T,order=1,mode='nearest',prefilter=False)

def encode_frame(dst,verts,normals,faces,drops,white,diagnostic,extent,foam):
    # 6 uint32 header, then normalized integer arrays; no renderer-specific bytes.
    vv=np.rint(np.clip(verts/extent,0,1)*65535).astype('<u2')
    nn=np.rint(np.clip(normals,-1,1)*32767).astype('<i2')
    dp=np.rint(np.clip(drops/extent,0,1)*65535).astype('<u2')
    dg=np.rint(np.clip(diagnostic/extent,0,1)*65535).astype('<u2')
    body=struct.pack('<6I',0x43465232,len(verts),len(faces),len(drops),len(white),len(diagnostic))
    body+=vv.tobytes()+nn.tobytes()+np.rint(np.clip(foam,0,1)*255).astype('u1').tobytes()+np.asarray(faces,dtype='<u4').tobytes()+dp.tobytes()
    body+=np.asarray(white,dtype='<f4').tobytes()+dg.tobytes()
    with gzip.open(dst,'wb',compresslevel=3) as f:f.write(body)

class Whitewater:
    """Persistent one-way secondary particles, driven by resolved liquid motion.
    State 0=foam (surface-projected), 1=spray (gravity/drag), 2=bubble (buoyant).
    Birth thresholds are an artistic subgrid heuristic, not resolved two-phase air.
    """
    def __init__(self,seed):
        self.rng=np.random.default_rng(seed);self.p=np.empty((0,3),np.float32)
        self.v=np.empty((0,3),np.float32);self.life=np.empty(0,np.float32)
        self.mode=np.empty(0,np.int32);self.radius=np.empty(0,np.float32);self.previous=None
        self.births=0
    def step(self,p,v,rho,vel,spacing,h,dt,iso,extent):
        gradients=np.gradient(rho,spacing)
        if len(self.p):
            rr=sample(rho,self.p,spacing)
            flow=np.column_stack([sample(a,self.p,spacing) for a in vel])
            air=(rr<iso*.65);deep=(rr>iso*1.8)
            self.mode[air]=1;self.mode[deep]=2;self.mode[~air&~deep]=0
            spray=self.mode==1;other=~spray
            self.v[spray,1]-=9.81*dt;self.v[spray]*=np.exp(-.2*dt)
            self.v[other]=flow[other];self.v[self.mode==2,1]+=.28
            self.p+=self.v*dt
            foam=self.mode==0
            if np.any(foam):
                pp=self.p[foam];val=sample(rho,pp,spacing)
                grad=np.column_stack([sample(g,pp,spacing) for g in gradients])
                inv=1/np.maximum(np.sum(grad*grad,axis=1),1)
                correction=(val-iso)[:,None]*grad*inv[:,None]
                correction=np.clip(correction,-h*.3,h*.3)
                self.p[foam]-=correction
            self.life-=dt
            keep=(self.life>0)&np.all(self.p>h*.85,axis=1)&np.all(self.p<extent-h*.85,axis=1)
            self.p=self.p[keep];self.v=self.v[keep];self.life=self.life[keep];self.mode=self.mode[keep];self.radius=self.radius[keep]
        # Find energetic surface particles, including collision/deceleration sites.
        ids=self.rng.choice(len(p),min(6500,len(p)),replace=False)
        pp=p[ids];vv=v[ids];den=sample(rho,pp,spacing);speed=np.linalg.norm(vv,axis=1)
        grad=np.column_stack([sample(g,pp,spacing) for g in gradients]);gn=np.linalg.norm(grad,axis=1)
        normal=-grad/np.maximum(gn[:,None],1e-6)
        outward=np.einsum('ij,ij->i',normal,vv)
        accel=np.zeros(len(ids))
        if self.previous is not None:
            valid=ids<len(self.previous);accel[valid]=np.linalg.norm(vv[valid]-self.previous[ids[valid]],axis=1)/dt
        score=np.maximum(0,speed-1.5)*np.maximum(0,accel-4)
        eligible=(den>iso*.65)&(den<iso*1.9)&(gn>3)&((score>8)|(outward>1.5))&(pp[:,1]>h*2)
        candidates=np.flatnonzero(eligible)
        if len(candidates):
            number=min(85,len(candidates),max(0,14000-len(self.p)))
            take=self.rng.choice(candidates,number,replace=False)
            pos=pp[take]+normal[take]*h*.15
            vv2=vv[take]+normal[take]*self.rng.uniform(.02,.25,(number,1))
            self.p=np.concatenate([self.p,pos]);self.v=np.concatenate([self.v,vv2])
            self.life=np.r_[self.life,self.rng.uniform(.55,2.3,number)].astype(np.float32)
            self.mode=np.r_[self.mode,np.zeros(number,np.int32)]
            self.radius=np.r_[self.radius,self.rng.uniform(.003,.009,number)].astype(np.float32)
            self.births+=number
        self.previous=v.copy()
        if not len(self.p):return np.empty((0,6),np.float32)
        alpha=np.minimum(1,self.life/.25)
        return np.column_stack([self.p,self.radius,self.mode,alpha]).astype(np.float32)

def main(name):
    folder=ROOT/'cache'/name
    manifest=json.loads((folder/'manifest.json').read_text());config=manifest['config'];h=config['h']
    spacing=h*.46;extent=np.array(config['extent'],np.float32)
    shape=tuple((np.ceil(extent/spacing).astype(int)+1).tolist())
    ww=Whitewater(config['seed']+99);stats=[];start=time.time()
    # Kernel integral puts bulk rest density near 4.38 at 8 particles per cell.
    iso=1.90
    for info in manifest['frames']:
        f=info['frame'];n=info['particles']
        a=np.fromfile(folder/f'{f:04d}.particles',dtype='<f4');p=a[:n*3].reshape(-1,3);v=a[n*3:].reshape(-1,3)
        rho,vx,vy,vz=deposit(p,v,shape,spacing,h*.98)
        # Small spatial filter only; temporal geometry comes from every new particle state.
        rho=gaussian_filter(rho,.42,mode='constant').astype(np.float32)
        verts,faces,_,_=marching_cubes(rho,level=iso,spacing=(spacing,spacing,spacing),gradient_direction='ascent',allow_degenerate=False)
        verts,normals=smooth_mesh(verts.astype(np.float32),faces.astype(np.int32),2)
        # Check orientation against decreasing density (outward normal).
        pick=np.arange(0,len(verts),max(1,len(verts)//2000));eps=spacing*.25
        outside=sample(rho,verts[pick]+normals[pick]*eps,spacing)
        inside=sample(rho,verts[pick]-normals[pick]*eps,spacing)
        if np.mean(outside-inside)>0:
            normals*=-1;faces=faces[:,[0,2,1]]
        density=sample(rho,p,spacing)
        drops=p[(density<iso*1.02)&(p[:,1]>.18)]
        if len(drops)>10000:drops=drops[np.linspace(0,len(drops)-1,10000).astype(int)]
        white=ww.step(p,v,rho,(vx,vy,vz),spacing,h,manifest['frameDt'],iso,extent)
        diagnostic=p[np.linspace(0,len(p)-1,min(14000,len(p))).astype(int)]
        target=folder/f'{f:04d}.mesh.gz'
        foam=np.zeros(len(verts),np.float32)
        if len(white):
            fp=white[white[:,4]==0,:3]
            if len(fp):
                dist,_=cKDTree(fp).query(verts,k=min(4,len(fp)),workers=1)
                if dist.ndim==1:dist=dist[:,None]
                foam=np.clip(np.sum(np.maximum(0,1-dist/(h*1.5))**2,axis=1)*.44,0,.9)
        encode_frame(target,verts,normals,faces,drops,white,diagnostic,extent,foam)
        s={'frame':f,'vertices':len(verts),'triangles':len(faces),'primaryDroplets':len(drops),'secondaryParticles':len(white),'bytes':target.stat().st_size}
        stats.append(s)
        if f%16==0:print(name,s,'wall',round(time.time()-start,1),flush=True)
    manifest['surface']={'method':'compact particle kernel + isosurface + 2 Taubin iterations','spacing':spacing,'kernelRadius':h*.98,'isovalue':iso,'shape':shape}
    manifest['whitewater']={'method':'persistent advected secondary particles; heuristic births; foam/spray/bubble states','totalBirths':ww.births,'twoWayCoupling':False}
    manifest['meshes']=stats;manifest['meshWallSeconds']=time.time()-start
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2));print('MESH COMPLETE',name,time.time()-start,flush=True)
if __name__=='__main__':
    for name in sys.argv[1:] or ['breach']:main(name)
