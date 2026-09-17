"""World-space guided DBM discharges and a transported, illuminated aerosol.

The electrodes and conductivity corridor are authored bending controls. Trees
grow in image/world space, rather than being warped from a straight strip.
This is a graphics model, not a calibrated plasma or shock-wave solver.
"""
import os
os.environ.setdefault('NUMBA_NUM_THREADS','2')
from pathlib import Path
import json,sys,time,math,subprocess
import numpy as np
import cv2
from scipy.ndimage import gaussian_filter, distance_transform_edt, map_coordinates
from scipy.fft import rfftn,irfftn
from numba import njit
from PIL import Image
from shared_motion import pose

R=Path(__file__).resolve().parent;B=R/'bending-rebuild-v3';B.mkdir(exist_ok=True)
OUT=B/'lightning-frames';OUT.mkdir(exist_ok=True)
W,H,FPS=1920,1080,30
cv2.setNumThreads(2)
EVENTS=np.array([.20,.38,.59,.79,1.015,1.235,1.46,1.665,1.845])

def xy(p,w,h):
    return np.column_stack(((p[:,0]/10.5+.5)*(w-1),(.5-(p[:,1]-1.903125)/5.90625)*(h-1)))

@njit(cache=True)
def relax(phi,kappa,occupied,iterations):
    h,w=phi.shape;err=0.
    for _ in range(iterations):
        err=0.
        for parity in range(2):
            for y in range(1,h-1):
                for x in range(1+(y+parity)%2,w-1,2):
                    if occupied[y,x]:continue
                    l=.5*(kappa[y,x]+kappa[y,x-1]);r=.5*(kappa[y,x]+kappa[y,x+1]);u=.5*(kappa[y,x]+kappa[y-1,x]);d=.5*(kappa[y,x]+kappa[y+1,x])
                    target=(l*phi[y,x-1]+r*phi[y,x+1]+u*phi[y-1,x]+d*phi[y+1,x])/(l+r+u+d)
                    change=1.65*(target-phi[y,x]);phi[y,x]+=change;err=max(err,abs(change))
        if err<1e-6:break
    return err

@njit(cache=True)
def grow(kappa,root,target,seed):
    np.random.seed(seed);h,w=kappa.shape
    phi=np.zeros((h,w),np.float64);occ=np.zeros((h,w),np.uint8)
    occ[0,:]=1;occ[-1,:]=1;occ[:,0]=1;occ[:,-1]=1
    tx,ty=target;rx,ry=root
    for y in range(ty-2,ty+3):
        for x in range(tx-2,tx+3):
            if (x-tx)**2+(y-ty)**2<=4:occ[y,x]=2;phi[y,x]=1
    nodes=np.full((w*h,2),-1,np.int32);parents=np.full(w*h,-1,np.int32)
    owner=np.full((h,w),-1,np.int32);front=np.zeros((h,w),np.uint8)
    nodes[0]=root;occ[ry,rx]=1
    moves=np.array([[1,0],[1,1],[0,1],[-1,1],[-1,0],[-1,-1],[0,-1],[1,-1]])
    for dx,dy in moves:front[ry+dy,rx+dx]=1;owner[ry+dy,rx+dx]=0
    relax(phi,kappa,occ,2500);n=1;end=-1;err=0.
    for step in range(12000):
        err=relax(phi,kappa,occ,25 if step%20 else 120)
        xx=np.empty(w*h,np.int32);yy=np.empty(w*h,np.int32);weights=np.empty(w*h,np.float64);total=0.;count=0
        for y in range(1,h-1):
            for x in range(1,w-1):
                if front[y,x] and occ[y,x]!=1:
                    weight=max(phi[y,x],0)**.65 * kappa[y,x]**.20
                    total+=weight;weights[count]=total;xx[count]=x;yy[count]=y;count+=1
        if total<1e-30:break
        pick=np.searchsorted(weights[:count],np.random.random()*total);x=xx[pick];y=yy[pick]
        nodes[n]=[x,y];parents[n]=owner[y,x]
        if (x-tx)**2+(y-ty)**2<=6:end=n;n+=1;break
        occ[y,x]=1;phi[y,x]=0;front[y,x]=0
        for dx,dy in moves:
            px=x+dx;py=y+dy
            if 0<px<w-1 and 0<py<h-1 and not occ[py,px] and not front[py,px]:front[py,px]=1;owner[py,px]=n
            elif occ[py,px]==2 and not front[py,px]:front[py,px]=1;owner[py,px]=n
        n+=1
    return nodes[:n],parents[:n],end,err

def network(event):
    path=B/f'world-staged-dbm-{event:02d}.npz'
    if path.exists():
        z=np.load(path);return {k:z[k] for k in z.files}
    at=EVENTS[event];end=min(1.68,at);start=max(.081,end-.80)
    guide=np.array([pose(t)[0] for t in np.linspace(start,end,180)])
    # Solve in a padded world-space region around the actual moving electrode.
    g=xy(guide,420,236);lower=np.maximum([1,1],np.floor(g.min(0)-29)).astype(int);upper=np.minimum([419,235],np.ceil(g.max(0)+29)).astype(int)
    width,height=(upper-lower).astype(int);line=np.zeros((height,width),np.uint8)
    cv2.polylines(line,[np.rint(g-lower).astype(np.int32)],False,1,1)
    dist=distance_transform_edt(1-line);rng=np.random.default_rng(1177+event)
    texture=gaussian_filter(rng.normal(size=(height,width)),2.0);texture/=max(.001,texture.std())
    kappa=(.10+np.exp(-(dist/15)**2))*np.exp(texture*.75)
    root=np.rint(g[0]-lower).astype(np.int32);target=np.rint(g[-1]-lower).astype(np.int32)
    begun=time.time();allnodes=[];allparents=[];previousTip=-1;error=0.
    # Sequential field targets implement the bending force without deforming
    # a finished straight-channel tree. Intermediate conductors follow actual
    # world coordinates and preserve the substantial side forks they grow.
    stops=np.linspace(start,end,max(2,int(np.ceil((end-start)/.19))+1))
    for part in range(len(stops)-1):
        seg=np.array([pose(stops[part])[0],pose(stops[part+1])[0]])
        endpoints=np.rint(xy(seg,420,236)-lower).astype(np.int32)
        ns,ps,tip,error=grow(kappa,endpoints[0],endpoints[1],7151+event*991+part*79)
        if tip<0:raise RuntimeError(f'Growth failed at event {event}, stage {part}')
        offset=len(allnodes);ps=ps+offset;ps[0]=previousTip
        allnodes.extend(ns.tolist());allparents.extend(ps.tolist());previousTip=tip+offset
    nodes=np.array(allnodes);parent=np.array(allparents);tip=previousTip
    trunk=np.zeros(len(nodes),bool);i=tip
    while i>=0:trunk[i]=True;i=parent[i]
    children=[[] for _ in parent]
    for i in range(1,len(parent)):children[parent[i]].append(i)
    depth=np.ones(len(parent),int)
    for i in range(len(parent)-1,0,-1):depth[parent[i]]=max(depth[parent[i]],depth[i]+1)
    strength=np.full(len(parent),.001);strength[trunk]=1
    def light(root,amp):
        total=depth[root];j=root
        while True:
            strength[j]=max(strength[j],amp*(depth[j]/total)**.7)
            if not children[j]:break
            j=max(children[j],key=lambda c:depth[c])
    for i in range(1,len(parent)):
        if not trunk[i] and trunk[parent[i]] and depth[i]>6:light(i,min(.48,depth[i]*.016))
    for i in range(1,len(parent)):
        if strength[i]<.005 and strength[parent[i]]>.08 and depth[i]>7:light(i,.07)
    pixels=(nodes+lower).astype(float)+rng.uniform(-.25,.25,nodes.shape)
    middle=np.array([i for i in range(1,len(parent)) if len(children[i])==1]);nxt=np.array([children[i][0] for i in middle])
    for _ in range(2):
        p=pixels.copy();p[middle]=.5*pixels[middle]+.25*(pixels[parent[middle]]+pixels[nxt]);pixels=p
    points=np.column_stack(((pixels[:,0]/419-.5)*10.5,1.903125+(.5-pixels[:,1]/235)*5.90625))
    result={'points':points,'parent':parent,'trunk':trunk,'strength':strength,'residual':np.array(error),'depth':depth}
    np.savez_compressed(path,**result);print('WORLD DBM',event,len(nodes),'main',int(trunk.sum()),'seconds',round(time.time()-begun,1),flush=True)
    return result

def exposure(f,at):
    t=f/FPS;t1=(f+1)/FPS;main=0.;fork=0.
    for offset,power,duration in [(0,1.,.009),(.044,.52,.006),(.101,.28,.005)]:
        overlap=max(0,min(t1,at+offset+duration)-max(t,at+offset))*FPS
        main+=power*overlap;fork+=power*overlap*(1 if offset==0 else .12)
    leader=max(0,min(t1,at)-max(t,at-.025))*FPS*.015
    return main+leader,fork+leader

def channel(f,nets,width=W,height=H):
    field=np.zeros((height,width),np.float32);peak=0.;event_active=-1
    for i,at in enumerate(EVENTS):
        energy,branch=exposure(f,at)
        if not energy:continue
        peak=max(peak,energy);event_active=i
        net=nets[i];p=np.rint(xy(net['points'],width,height)).astype(np.int32)
        for j in range(1,len(p)):
            power=(energy if net['trunk'][j] else branch)*net['strength'][j]
            if net['trunk'][j]:power*=.8+.45*(net['depth'][j]/net['depth'][0])**.6
            if power<.0001:continue
            cv2.line(field,tuple(p[net['parent'][j]]),tuple(p[j]),float(power),max(1,round(width/W*1.3)) if net['trunk'][j] else 1,cv2.LINE_AA)
    return field,peak,event_active

class Haze:
    """Low-density aerosol tracer; 3D advection, buoyancy, FFT projection."""
    def __init__(self):
        self.shape=(40,112,200);self.spacing=np.array([1.5/39,5.90625/111,10.5/199])
        self.coord=np.indices(self.shape,dtype=np.float32);self.v=np.zeros((3,*self.shape),np.float32);self.rho=np.zeros(self.shape,np.float32);self.heat=np.zeros(self.shape,np.float32)
        rng=np.random.default_rng(8719);noise=gaussian_filter(rng.random(self.shape).astype(np.float32),2);noise=(noise-noise.min())/(noise.max()-noise.min())
        self.noise=np.exp((noise-.5)*6);self.zz=(self.coord[0]-19.5)*self.spacing[0]
        k=np.meshgrid(*[np.sin(2*np.pi*(np.fft.rfftfreq(n) if i==2 else np.fft.fftfreq(n)))/self.spacing[i] for i,n in enumerate(self.shape)],indexing='ij')
        self.k=np.array(k);self.k2=np.sum(self.k*self.k,axis=0);self.k2[0,0,0]=1
        self.rows=[]
        # Divergence-free initial ambient eddies from a random vector potential.
        a=np.stack([gaussian_filter(rng.normal(size=self.shape),4) for _ in range(3)]).astype(np.float32)
        self.v[0]=(np.gradient(a[2],self.spacing[1],axis=1)-np.gradient(a[1],self.spacing[2],axis=2))*.9
        self.v[1]=(np.gradient(a[0],self.spacing[2],axis=2)-np.gradient(a[2],self.spacing[0],axis=0))*.9
        self.v[2]=(np.gradient(a[1],self.spacing[0],axis=0)-np.gradient(a[0],self.spacing[1],axis=1))*.9
        self.last=np.zeros(self.shape,np.float32)
    def step(self,f,nets):
        small,peak,event=channel(f,nets,200,112)
        source=gaussian_filter(small,1.1)[None]*np.exp(-(self.zz/.13)**2)
        p,d,on,_=pose(f/30);px,py=xy(np.array([p]),200,112)[0]
        nozzle=np.exp(-((self.coord[2]-px)*self.spacing[2]/.32)**2-((self.coord[1]-py)*self.spacing[1]/.32)**2-(self.zz/.24)**2)*self.noise
        for _ in range(2):
            dt=1/60
            lookup=self.coord-self.v*dt/self.spacing[:,None,None,None]
            self.rho=map_coordinates(self.rho,lookup,order=1,mode='constant')
            self.heat=map_coordinates(self.heat,lookup,order=1,mode='constant')
            self.v=np.stack([map_coordinates(v,lookup,order=1,mode='constant') for v in self.v])
            self.rho+=nozzle*(.34*dt*on);self.rho*=np.exp(-.70*dt)
            self.heat+=source*10*dt;self.heat*=np.exp(-3.0*dt)
            self.v[1]-=(self.heat*5+self.rho*.7)*dt;self.v[2]+=nozzle*.15*dt
            spectra=np.stack([rfftn(v,workers=2) for v in self.v]);dot=np.sum(spectra*self.k,axis=0)/np.maximum(self.k2,1e-12)
            spectra-=self.k*dot;self.v=np.stack([irfftn(v,s=self.shape,workers=2) for v in spectra]).astype(np.float32)
        # Single-scattering approximation: inverse-square channel illumination
        # through the transported aerosol, integrated in camera depth.
        self.last*=np.exp(-1/30*7)
        if peak>0:
            mask=np.broadcast_to(small[None]>.01,self.shape)&(abs(self.zz)<.07)
            if mask.any():
                distance=distance_transform_edt(~mask,sampling=self.spacing)
                light=peak*np.exp(-distance/1.1)/(.025+distance*distance)
                self.last=np.maximum(self.last,light.astype(np.float32))
        scatter=np.sum(self.rho*self.last,axis=0)*self.spacing[0]
        if f%15==0:self.rows.append({'frame':f,'aerosolMass':float(self.rho.sum()*np.prod(self.spacing)),'maximumSpeed':float(np.linalg.norm(self.v,axis=0).max()),'finite':bool(np.isfinite(self.v).all())})
        return cv2.resize(scatter,(W,H),interpolation=cv2.INTER_CUBIC)

def render(f,nets,haze):
    field,peak,_=channel(f,nets,W*2,H*2);core=cv2.resize(field,(W,H),interpolation=cv2.INTER_AREA)*55
    near=cv2.GaussianBlur(core,(0,0),.7);halo=cv2.GaussianBlur(core,(0,0),4.5);wide=cv2.GaussianBlur(core,(0,0),19)
    scatter=haze.step(f,nets)
    linear=core[:,:,None]*np.array([1,.98,1])+near[:,:,None]*[.25,.27,.34]+halo[:,:,None]*[.065,.085,.16]+wide[:,:,None]*[.02,.03,.075]+scatter[:,:,None]*[.25,.34,.53]
    rgb=1-np.exp(-np.maximum(linear,0));rgb=np.where(rgb<=.0031308,12.92*rgb,1.055*rgb**(1/2.4)-.055)
    return np.rint(np.clip(rgb,0,1)*255).astype(np.uint8)

if __name__=='__main__':
    started=time.time();nets=[network(i) for i in range(len(EVENTS))]
    if '--networks' in sys.argv:sys.exit(0)
    full='--full' in sys.argv;haze=Haze();encoder=None
    if full:encoder=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r','30','-i','-','-c:v','libx264','-preset','slow','-crf','15','-pix_fmt','yuv420p','-movflags','+faststart',str(B/'lightning-v3.mp4')],stdin=subprocess.PIPE)
    for f in range(120 if full else 60):
        pixels=render(f,nets,haze)
        if encoder:encoder.stdin.write(pixels.tobytes())
        if f in [18,24,30,37,38,39,44,50,56,65,80,105]:Image.fromarray(pixels).resize((1280,720),Image.Resampling.LANCZOS).save(OUT/f'{f:04d}.jpg',quality=95)
        if f%15==0:print('LIGHTNING FRAME',f,'seconds',round(time.time()-started,1),flush=True)
    if encoder:encoder.stdin.close();assert encoder.wait()==0
    (B/'lightning-report.json').write_text(json.dumps({'model':__doc__,'nodes':[len(n['points']) for n in nets],'haze':haze.rows,'frames':120 if full else 60,'elapsed':time.time()-started},indent=2))
    print('COMPLETE',round(time.time()-started,1),flush=True)
