"""Guided dielectric-breakdown growth and exposure-integrated discharge rendering.

A CPU Laplace field selects stochastic growth sites on the conductor frontier.
The resulting trees are mapped into the shared bending corridor. This is a
graphics DBM with an authored corridor, not a calibrated 3-D plasma simulation.
Reference: Kim & Lin, Physically Based Animation and Rendering of Lightning (2004).
https://gamma-web.iacs.umd.edu/LIGHTNING/lightning.pdf
"""
import os
os.environ.setdefault('NUMBA_NUM_THREADS','2')
from pathlib import Path
import sys,json,time,math,subprocess
import numpy as np
import cv2
from numba import njit
from scipy.ndimage import gaussian_filter
from PIL import Image
from shared_motion import pose,DATA

R=Path(__file__).resolve().parent;B=R/'bending-rebuild-v2';B.mkdir(exist_ok=True)
OUT=B/'lightning-frames';OUT.mkdir(exist_ok=True)
cv2.setNumThreads(2)
NX,NY=420,144
W,H,SS,FPS=1920,1080,2,30

@njit(cache=True)
def relax(phi,occupied,iterations):
    h,w=phi.shape;error=0.
    for it in range(iterations):
        error=0.
        for parity in range(2):
            for y in range(1,h-1):
                for x in range(1+(y+parity)%2,w-1,2):
                    if occupied[y,x]:continue
                    target=.25*(phi[y-1,x]+phi[y+1,x]+phi[y,x-1]+phi[y,x+1])
                    delta=1.65*(target-phi[y,x]);phi[y,x]+=delta
                    error=max(error,abs(delta))
        if error<2e-6:break
    return error

@njit(cache=True)
def growth(seed):
    np.random.seed(seed)
    phi=np.zeros((NY,NX),np.float64)
    occupied=np.zeros((NY,NX),np.uint8)
    occupied[0,:]=1;occupied[-1,:]=1;occupied[:,0]=1;occupied[:,-1]=1
    # A distant positive electrode; grounded growing channel and outer walls.
    phi[NY//2-8:NY//2+9,-1]=1.
    nodes=np.full((NX*NY,2),-1,np.int32);parent=np.full(NX*NY,-1,np.int32)
    indices=np.full((NY,NX),-1,np.int32);front=np.zeros((NY,NX),np.uint8)
    nodes[0]=[3,NY//2];indices[NY//2,3]=0;occupied[NY//2,3]=1
    moves=np.array([[1,0],[1,1],[0,1],[-1,1],[-1,0],[-1,-1],[0,-1],[1,-1]])
    for dx,dy in moves:front[NY//2+dy,3+dx]=1
    relax(phi,occupied,2400)
    n=1;success=-1;last_error=0.
    for step in range(25000):
        last_error=relax(phi,occupied,36 if step%15 else 160)
        weights=np.empty(NX*NY,np.float64);xx=np.empty(NX*NY,np.int32);yy=np.empty(NX*NY,np.int32)
        total=0.;c=0
        for y in range(1,NY-1):
            for x in range(1,NX-1):
                if front[y,x] and not occupied[y,x]:
                    weight=max(phi[y,x],0)**.85
                    # Small nonzero forward bias is an authored guide, not a
                    # hand-drawn centerline or post-generated side branches.
                    weight*=.8+.4*x/NX
                    total+=weight;weights[c]=total;xx[c]=x;yy[c]=y;c+=1
        if total<=1e-30:break
        choice=np.random.random()*total;idx=np.searchsorted(weights[:c],choice)
        x=xx[idx];y=yy[idx];best=-1
        for dx,dy in moves:
            near=indices[y+dy,x+dx]
            if near>best:best=near
        if best<0:break
        nodes[n]=[x,y];parent[n]=best;indices[y,x]=n;occupied[y,x]=1;front[y,x]=0;phi[y,x]=0
        for dx,dy in moves:
            px=x+dx;py=y+dy
            if px>0 and px<NX-1 and py>0 and py<NY-1 and not occupied[py,px]:front[py,px]=1
        if x>=NX-3:success=n;n+=1;break
        n+=1
    return nodes[:n],parent[:n],success,last_error

def network(seed):
    cache=B/f'lightning-dbm-wide-{seed}.npz'
    if cache.exists():
        z=np.load(cache);return {k:z[k] for k in z.files}
    started=time.time();nodes,parent,end,residual=growth(seed)
    if end<0:raise RuntimeError(f'DBM failed to connect: {len(nodes)} nodes')
    trunk=np.zeros(len(nodes),bool);i=end
    while i>=0:trunk[i]=True;i=parent[i]
    # Long secondary branches carry more light; very short dead-end tips remain
    # faint. The hierarchy is extracted from the grown tree, not added by hand.
    depth=np.ones(len(nodes),np.int32)
    for i in range(len(nodes)-1,0,-1):depth[parent[i]]=max(depth[parent[i]],depth[i]+1)
    order=np.zeros(len(nodes),np.int32)
    for i in range(1,len(nodes)):order[i]=0 if trunk[i] else order[parent[i]]+int(trunk[parent[i]])
    strength=np.where(trunk,1.,np.minimum(.68,.035+depth**.70*.036))
    rng=np.random.default_rng(seed+10000)
    xy=nodes.astype(float)+rng.uniform(-.33,.33,nodes.shape)
    u=np.clip((xy[:,0]-3)/(NX-6),0,1)
    # Arc-length-uniform source timing maps the solved conductor into the
    # artistic movement. Off-axis displacement carries actual grown branches.
    points=[]
    for f,y in zip(u,xy[:,1]):
        p,d,_,_=pose(.08+1.6*f)
        normal=np.array([-d[1],d[0]])
        points.append(p+normal*(y-NY/2)*(11.05/(NX-6)))
    points=np.array(points)
    result={'points':points,'parent':parent,'u':u,'strength':strength,'trunk':trunk,'depth':depth,'end':np.array(end),'residual':np.array(residual)}
    np.savez_compressed(cache,**result)
    print('DBM',seed,'nodes',len(nodes),'main',int(trunk.sum()),'seconds',round(time.time()-started,1),'residual',residual,flush=True)
    return result

def project(p):
    return np.column_stack(((p[:,0]/10.5+.5)*W*SS,(.5-(p[:,1]-1.903125)/5.90625)*H*SS)).astype(np.int32)

def prepare_network(net,seed):
    """Remove lattice appearance; preserve every solved junction and connection."""
    parent=net['parent'];depth=net['depth'];trunk=net['trunk']
    children=[[] for _ in parent]
    for i in range(1,len(parent)):children[parent[i]].append(i)
    point=net['points'].copy();rng=np.random.default_rng(seed+191)
    point+=rng.uniform(-.007,.007,point.shape)
    middle=np.array([i for i in range(1,len(parent)) if len(children[i])==1])
    next_node=np.array([children[i][0] for i in middle])
    for _ in range(2):
        new=point.copy();new[middle]=point[middle]*.48+(point[parent[middle]]+point[next_node])*.26;point=new
    strength=np.full(len(parent),.006)
    strength[trunk]=1.
    def illuminate(root,amplitude):
        total=max(1,depth[root]);j=root
        while True:
            strength[j]=max(strength[j],amplitude*(depth[j]/total)**.62)
            if not children[j]:break
            j=max(children[j],key=lambda x:depth[x])
    for i in range(1,len(parent)):
        if not trunk[i] and trunk[parent[i]] and depth[i]>=10:illuminate(i,.32*min(1,depth[i]/30))
    for i in range(1,len(parent)):
        if strength[i]<.01 and strength[parent[i]]>.12 and depth[i]>=9:illuminate(i,.075)
    net['points']=point;net['strength']=strength;net['pixels']=project(point)

def overlap(a,b,c,d):return max(0,min(b,d)-max(a,c))

def render(f,nets):
    t=f/FPS;t1=(f+1)/FPS
    field=np.zeros((H*SS,W*SS),np.float32)
    # Each event has a faint leader, a primary stroke, and weaker return
    # strokes through the same conductor. Exposure integrates their durations.
    for event,at in enumerate(np.arange(.14,1.98,.145)):
        energy=0.;branch_energy=0.
        for offset,power,duration in [(0,1.,.012),(.041,.57,.008),(.083,.29,.006)]:
            covered=overlap(t,t1,at+offset,at+offset+duration)*FPS
            energy+=covered*power
            branch_energy+=covered*power*(1 if offset==0 else .24)
        leader=overlap(t,t1,at-.019,at)*FPS*.035
        if energy+leader==0:continue
        net=nets[event%len(nets)];end=min(1.68,at);start=max(.08,end-.86)
        age=end-(.08+net['u']*1.6)
        active=(age>=0)&(age<end-start)
        pixels=net['pixels'];parent=net['parent'];strength=net['strength'];trunk=net['trunk']
        source_release=1. if at<1.70 else math.exp(-(at-1.70)*6)
        for i in np.flatnonzero(active):
            j=parent[i]
            if j<0 or not active[j]:continue
            power=(energy if trunk[i] else branch_energy)*strength[i]+leader*strength[i]
            if power<=0:continue
            power*=source_release*(.55+.45*math.exp(-age[i]*1.8))
            width=3 if trunk[i] else 1
            cv2.line(field,tuple(pixels[j]),tuple(pixels[i]),float(power*38),width,cv2.LINE_AA)
    core=cv2.resize(field,(W,H),interpolation=cv2.INTER_AREA)
    near=cv2.GaussianBlur(core,(0,0),.8)
    corona=cv2.GaussianBlur(core,(0,0),3.0)
    wide=cv2.GaussianBlur(core,(0,0),12.5)
    linear=core[:,:,None]*np.array([1,.97,1.])+near[:,:,None]*np.array([.30,.36,.58])+corona[:,:,None]*np.array([.12,.20,.51])+wide[:,:,None]*np.array([.06,.08,.20])
    # Exposure response and display transform; the unilluminated image is zero.
    rgb=1-np.exp(-linear)
    rgb=np.where(rgb<=.0031308,rgb*12.92,1.055*np.maximum(rgb,0)**(1/2.4)-.055)
    return np.rint(np.clip(rgb,0,1)*255).astype(np.uint8)

if __name__=='__main__':
    started=time.time();nets=[network(seed) for seed in [6251,8257,9173]]
    for i,net in enumerate(nets):prepare_network(net,194+i)
    pilot='--full' not in sys.argv
    frames=[20,21,35,41,42,45,50,57] if pilot else range(120)
    encoder=None
    if not pilot:
        encoder=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r','30','-i','-','-c:v','libx264','-preset','slow','-crf','15','-pix_fmt','yuv420p','-movflags','+faststart',str(B/'lightning-v2.mp4')],stdin=subprocess.PIPE)
    for f in frames:
        pixels=render(f,nets)
        if encoder:encoder.stdin.write(pixels.tobytes())
        if pilot or f%5==0:Image.fromarray(pixels).resize((1280,720),Image.Resampling.LANCZOS).save(OUT/f'{f:04}.jpg',quality=95)
    if encoder:
        encoder.stdin.close()
        if encoder.wait():raise RuntimeError('Encoder failed')
    (B/'lightning-report.json').write_text(json.dumps({'model':'CPU guided 2-D dielectric-breakdown tree, mapped to the authored shared path','full3DPlasmaSimulation':False,'reference':'https://gamma-web.iacs.umd.edu/LIGHTNING/lightning.pdf','networks':[{'nodes':len(n['points']),'trunkNodes':int(n['trunk'].sum()),'relaxationUpdate':float(n['residual'])} for n in nets],'frames':len(frames),'elapsed':time.time()-started},indent=2))
    print('LIGHTNING RENDER COMPLETE',round(time.time()-started,1),flush=True)
