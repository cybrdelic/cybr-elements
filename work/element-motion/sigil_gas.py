"""Guided 3D gas lettering: transported/reacting fields, pure black camera.
The artwork defines a timed gas supply. No image-space wordmark is composited.
"""
from pathlib import Path
import argparse, json, math, time, subprocess, os, shutil
os.environ.setdefault('OMP_NUM_THREADS','2')
import numpy as np, cv2, torch
import torch.nn.functional as F
from PIL import Image

p=argparse.ArgumentParser();p.add_argument('element',choices=['fire','air']);p.add_argument('variant',choices=['01','02']);p.add_argument('--size',nargs=3,type=int,default=[640,80,360]);p.add_argument('--ungated',action='store_true');p.add_argument('--cpu',action='store_true');p.add_argument('--pilot',action='store_true');a=p.parse_args()
R=Path(__file__).resolve().parent;B=R/'sigil-v1';O=B/f'{a.element}-{a.variant}';O.mkdir(exist_ok=True)
if a.pilot:O=O/'pilot';O.mkdir(exist_ok=True)
if shutil.disk_usage(B).free<1024**3:raise RuntimeError('1 GiB reserve required')
torch.set_num_threads(2);torch.set_grad_enabled(False);dev='cpu' if a.cpu else 'cuda'
if not a.cpu:torch.cuda.reset_peak_memory_stats()
D=np.load(B/f'mark-{a.variant}.npz');X,Y,Z=a.size;shape=(Z,Y,X);extent=[11.4,1.2,6.4125]
h=torch.tensor(np.array(extent)/(np.array(a.size)-1),device=dev,dtype=torch.float32)
zz,yy,xx=torch.meshgrid(torch.linspace(-1,1,Z,device=dev),torch.linspace(-1,1,Y,device=dev),torch.linspace(-1,1,X,device=dev),indexing='ij')
x=xx*5.7;y=yy*.6;z=zz*3.20625+2.95;grid=torch.stack([xx,yy,zz],-1)[None]
step_scale=(2/torch.tensor(extent,device=dev)).view(1,3,1,1,1);dt=1/120
mask=torch.from_numpy(cv2.resize(D['mask'].astype('f'),(X,Z),interpolation=cv2.INTER_AREA)).to(dev)[:,None,:]
arrival=torch.from_numpy(cv2.resize(D['arrival'],(X,Z),interpolation=cv2.INTER_LINEAR)).to(dev)[:,None,:]
distance=torch.from_numpy(cv2.resize(D['sdf'],(X,Z),interpolation=cv2.INTER_LINEAR)).to(dev)[:,None,:]
oxidizer=((distance+.040)/.060).clamp(0,1)
thin=torch.exp(-(y/.070)**2);supply=mask*thin
edge=torch.minimum(torch.minimum(1-xx.abs(),1-yy.abs()),1-zz.abs());sponge=(edge/.06).clamp(0,1)
state=torch.zeros((1,8,*shape),device=dev);state[:,4]=1
freq=[torch.fft.fftfreq(n,device=dev) for n in shape[:2]]+[torch.fft.rfftfreq(X,device=dev)]
kz,ky,kx=torch.meshgrid(*freq,indexing='ij');k=torch.stack([torch.sin(2*math.pi*kx)/h[0],torch.sin(2*math.pi*ky)/h[1],torch.sin(2*math.pi*kz)/h[2]]);k2=(k*k).sum(0).clamp_min(1e-12)
def derivative(q,axis,spacing):return (torch.roll(q,-1,axis)-torch.roll(q,1,axis))/(2*spacing)
def advect(q,v,sign=1):return F.grid_sample(q,grid-(v*step_scale*dt*sign).permute(0,2,3,4,1),align_corners=True,padding_mode='border')
def step(t):
    global state
    v=state[:,:3];moved=advect(state,v);returned=advect(moved,v,-1)
    corrected=moved[:,3:]+.5*(state[:,3:]-returned[:,3:]);upper=F.max_pool3d(state[:,3:],3,1,1);lower=-F.max_pool3d(-state[:,3:],3,1,1)
    departure=grid-(v*step_scale*dt).permute(0,2,3,4,1)
    upper=F.grid_sample(upper,departure,mode='nearest',padding_mode='border',align_corners=True);lower=F.grid_sample(lower,departure,mode='nearest',padding_mode='border',align_corners=True)
    moved[:,3:]=torch.maximum(lower,torch.minimum(upper,corrected)).clamp_min_(0);state=moved
    del moved,v,returned,corrected,upper,lower,departure
    v=state[0,:3];fuel,oxygen,temp,rho=[state[0,i] for i in [3,4,5,6]]
    active=((t-arrival)/.16).clamp(0,1);active=active*active*(3-2*active)
    source=supply*active*(1. if t<6.2 else 0.)
    variation=.82+.18*torch.sin(x*26+z*31+y*14-t*5)
    if a.element=='fire':
        injection=source*(dt*7)
        fuel.lerp_(torch.ones_like(fuel)*.9,injection);temp.lerp_(torch.ones_like(temp)*.8,injection)
        # An authored oxidizer field keeps the counterspaces open. Gas still
        # advects in 3D; after release the atmospheric boundary is restored.
        oxygen.lerp_(oxidizer.expand_as(oxygen) if t<6.2 else torch.ones_like(oxygen),dt*12)
        if t<6.2:oxygen.mul_(oxidizer)
        burn=torch.minimum(fuel,oxygen*.7)*(1-math.exp(-8*dt))*((temp-.12)/.25).clamp(0,1)
        fuel.sub_(burn);oxygen.sub_(burn/.7).clamp_(0,1);temp.add_(burn*5.5).mul_(math.exp(-1.5*dt));rho.add_(burn*.32).mul_(math.exp(-1.35*dt));state[0,7]=burn/dt
        # Bending support near the supply preserves counters during the hold.
        support=.91 if t<6.2 else 0.
        v[2].add_((temp*2.5-rho*.24)*(1-support)*dt)
    else:
        rho.lerp_(variation*.9,(source*dt*7).clamp(0,1));rho.mul_(math.exp(-.72*dt));fuel.zero_();temp.zero_();state[0,7].zero_()
        if t<6.2:rho.mul_(oxidizer)
        v[0].add_(.065*dt);v[2].add_(.015*dt)
    curl=torch.sin(x*13+z*17-t*3)*torch.cos(y*21+t*2)
    v[0].add_(source*curl*.55*dt);v[1].add_(source*torch.sin(x*17-z*13+t*4)*1.2*dt)
    v[2].add_(source*torch.cos(x*13+z*17-t*3)*.6*dt)
    # Move the reacting wake through depth, preserving the openings in the
    # camera plane. Gas exits through open depth boundaries, not an image mask.
    axial=(3.8 if a.element=='fire' else 2.0)+.65*torch.sin(x*19+z*13-t*4)
    if t<6.2:
        v[1].lerp_(axial,(source*dt*24).clamp(0,1))
    wx=derivative(v[2],1,h[1])-derivative(v[1],0,h[2]);wy=derivative(v[0],0,h[2])-derivative(v[2],2,h[0]);wz=derivative(v[1],2,h[0])-derivative(v[0],1,h[1])
    omega=torch.stack([wx,wy,wz]);mag=torch.linalg.vector_norm(omega,dim=0)
    grad=torch.stack([derivative(mag,2,h[0]),derivative(mag,1,h[1]),derivative(mag,0,h[2])]);grad/=torch.linalg.vector_norm(grad,dim=0).clamp_min(1e-6)
    v.add_(torch.linalg.cross(grad,omega,dim=0)*dt*.11);del wx,wy,wz,omega,mag,grad,source,active,curl,variation
    v.mul_(sponge)
    spectral=torch.fft.rfftn(v,dim=(-3,-2,-1));dot=(spectral*k).sum(0)/k2;spectral-=k*dot;spectral*=torch.exp(-k2*.000025*dt)
    v.copy_(torch.fft.irfftn(spectral,s=shape,dim=(-3,-2,-1)));state[:,3:4].mul_(sponge);state[:,5:].mul_(sponge);oxygen.lerp_(torch.ones_like(oxygen),1-sponge)

def render():
    rho=state[0,6]
    if a.element=='fire':
        reaction=state[0,7];hot=((state[0,5]-.28)/3.1).clamp(0,1);sigma=(rho*4.4+reaction*.025).clamp(0,16)
        color=torch.stack([torch.ones_like(hot),.035+.93*hot.pow(1.3),.002+.72*hot.pow(3)],-1)
        rgb=color*reaction.clamp_min(0).pow(.95)[...,None]*6.5
    else:
        sigma=rho.clamp_min(0).pow(1.24)*4.5
        top=torch.flip(torch.cumsum(torch.flip(sigma,[0]),0),[0])*h[2];side=torch.cumsum(sigma,2)*h[0]
        light=torch.exp(-top*1.3)*4.1+torch.exp(-side*1.4-top*.65)*.85+.11
        rgb=sigma[...,None]*light[...,None]*torch.tensor([.77,.86,1.],device=dev)/(4*math.pi)
    atten=torch.exp(-sigma*h[1]);transmission=torch.cat([torch.ones_like(atten[:,:1]),torch.cumprod(atten[:,:-1],1)],1)
    linear=(transmission[...,None]*rgb*(1-atten[...,None])/sigma[...,None].clamp_min(1e-6)).sum(1)
    linear=F.interpolate(linear.permute(2,0,1).flip(1)[None],size=(1080,1920),mode='bicubic',align_corners=False).clamp_min(0)
    if a.element=='fire':
        glow=F.avg_pool2d(F.avg_pool2d(linear,(1,19),1,(0,9)),(19,1),1,(9,0));linear=(linear+glow*.014)*.20
    else:linear*=1.35
    rgb=(linear*(2.51*linear+.03)/(linear*(2.43*linear+.59)+.14)).clamp(0,1)
    rgb=torch.where(rgb<=.0031308,rgb*12.92,1.055*rgb.pow(1/2.4)-.055)
    return (rgb[0].permute(1,2,0)*255).byte().cpu().numpy()

enc=None if a.pilot else subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','-','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(B/f'{a.element}-{a.variant}.mp4')],stdin=subprocess.PIPE)
start=time.time();rows=[]
for f in range(121 if a.pilot else 300):
    for sub in range(4):step((f+sub/4)/30)
    pixels=render() if not a.pilot or f in [20,60,96,120] else None
    if enc:enc.stdin.write(pixels.tobytes())
    if f in [20,60,96,120,150,180,210,240,270,299]:Image.fromarray(pixels).resize((1440,810)).save(O/f'{f:04}.jpg',quality=94)
    if f%30==0:
        v=state[0,:3];div=derivative(v[0],2,h[0])+derivative(v[1],1,h[1])+derivative(v[2],0,h[2]);row=dict(frame=f,seconds=round(time.time()-start,1),finite=bool(torch.isfinite(state).all()),divergence=float(div.square().mean().sqrt()),gpuMiB=0 if a.cpu else round(torch.cuda.max_memory_allocated()/1048576));rows.append(row);print(json.dumps(row),flush=True)
        assert row['finite'] and row['gpuMiB']<6900
    if f==120 and not a.ungated and not a.pilot:
        print('REVIEW GATE '+a.element+' '+a.variant,flush=True)
        while not (B/f'continue-{a.element}-{a.variant}').exists():time.sleep(.5)
if enc:enc.stdin.close();assert enc.wait()==0
(O/'report.json').write_text(json.dumps(dict(element=a.element,variant=a.variant,frames=121 if a.pilot else 300,fps=30,grid=a.size,method='Projected 3D velocity, limited MacCormack scalar advection; registered glyph gas supply, authored oxidizer/tracer boundary during hold; fuel/oxygen reaction for fire, passive tracer for air; source shutoff at 6.2s, no image fade',rows=rows,seconds=time.time()-start),indent=2),encoding='utf-8')
print('COMPLETE',flush=True)
