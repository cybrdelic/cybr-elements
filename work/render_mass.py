"""VFX transport of the scene's native flame radiance, with inertial parcels.

Not a new coupled CFD solve: cached native fire supplies the material; a finite
arrival force carries parcels through a momentary typographic arrangement.
No fuel stencil, letter mesh, perpetual nozzle, or stationary velocity channel.
"""
import os, json, time, math, subprocess
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter
from PIL import Image
from flow_paths import paths

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'mass-frames';OUT.mkdir(exist_ok=True)
torch.set_grad_enabled(False);torch.set_num_threads(2)
device='cuda';FPS=30;SECONDS=float(os.environ.get('MASS_SECONDS','6.5'))
W=int(os.environ.get('MASS_WIDTH','1280'));H=W*9//16
scale=W/10.7
rng=np.random.default_rng(7421)
curves=paths()
N_S=640;N_V=64
arrays={k:[] for k in ['target','initial','end_v','uv','area','phase','texphase','tip']}
for j,curve in enumerate(curves):
    p=curve['points'].copy();p[:,1]-=1.95
    lengths=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    ss=(np.arange(N_S)+.5)/N_S
    cc=np.stack([np.interp(ss*lengths[-1],lengths,p[:,k]) for k in range(2)],axis=-1)
    tt=np.gradient(cc,axis=0);tt/=np.maximum(np.linalg.norm(tt,axis=1)[:,None],1e-9)
    vv=(np.arange(N_V)+.5)/N_V*2-1
    s,v=np.meshgrid(ss,vv,indexing='ij')
    normal=np.stack([-tt[:,1],tt[:,0]],axis=-1)
    def eddy(sigma):
        q=gaussian_filter(rng.normal(size=s.shape),sigma=sigma)
        return q/max(float(q.std()),1e-6)
    width=.17*np.clip(1+eddy((26,20))*.18,.6,1.5)
    fray=.012*eddy((14,10))+.005*eddy((4,4))
    target=cc[:,None,:]+normal[:,None,:]*(v*width+fray)[...,None]
    target+=tt[:,None,:]*(.012*eddy((17,12)))[...,None]
    # One flame mass starts on the left, not at the letters.
    init=np.stack([-5.2+s*2.1+.04*eddy((18,12)),.15+.48*v+.20*np.sin(s*math.pi)+.03*eddy((15,10))],axis=-1)
    endv=tt[:,None,:]*(.68+.12*np.sin(s*31+j))[...,None]+normal[:,None,:]*(.25*np.sin(s*27+j+v))[...,None]
    # Neighbouring material parcels keep coherent native flame texture.
    uv=np.stack([70+v*43,195+s*104],axis=-1)
    area=np.ones(s.shape)*(lengths[-1]/N_S)*(.38/N_V)*scale**2
    arrays['target'].append(target.reshape(-1,2))
    arrays['initial'].append(init.reshape(-1,2))
    arrays['end_v'].append(endv.reshape(-1,2))
    arrays['uv'].append(uv.reshape(-1,2))
    arrays['area'].append(area.ravel())
    arrays['phase'].append(np.full(s.size,j*1.37)+s.ravel()*8+v.ravel()*2)
    arrays['texphase'].append((s*lengths[-1]/.48+j*.317).ravel())
    arrays['tip'].append((np.minimum(1,s/.035)*np.minimum(1,(1-s)/.035)).ravel())

def tensor(v):return torch.tensor(v,dtype=torch.float32,device=device)
data={k:tensor(np.concatenate(v)) for k,v in arrays.items()}
pos=data['initial'].clone();vel=torch.zeros_like(pos);vel[:,0]=3.0
target=data['target'];endv=data['end_v'];phase=data['phase'];uv=data['uv'];area=data['area']
native=tensor(np.stack([np.load(ROOT/'native-flame'/f'{i:03d}.npy').astype(np.float32) for i in range(24)]))
texture_grid=torch.stack([uv[:,0]/263*2-1,uv[:,1]/319*2-1],dim=-1)[None,None]
T=2.65
# A camera speed ramp stretches the short alignment, not a stationary hold.
clock=PchipInterpolator([0,1.7,2.6,3.8,5.2,6.5],[0,2.12,2.50,2.78,4.25,5.60])
prev=0.;started=time.monotonic();checks=[]
video=ROOT.parent/'outputs'/'cybrdelic-fire-momentum.mp4'
encoder=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],stdin=subprocess.PIPE)

def advance(u,delta):
    global pos,vel
    n=max(1,math.ceil(delta/.009));dt=delta/n
    for step in range(n):
        now=u-delta+(step+1)*dt
        if now<1.1:
            vel[:,1].add_(torch.sin(pos[:,0]*3+phase*.15+now*4)*(.28*dt))
        elif now<T-.04:
            remaining=T-now
            acc=6*(target-pos)/(remaining*remaining)-(4*vel+2*endv)/remaining
            # The finite arrival force changes momentum, never positions.
            vel.add_(acc*dt)
        else:
            q=pos
            age=max(0.,now-T)
            curl=torch.stack([torch.sin(q[:,1]*5+now*3+phase*.1),torch.cos(q[:,0]*4-now*2+phase*.1)],dim=1)
            vel.add_((curl*(.22+min(age,1.5)*.4)+tensor([1.65,1.05])*min(age*1.8,1.))*dt)
        pos.add_(vel*dt)

def image(u,frame):
    # Interpolate actual cached fire frames; retain their ragged flame detail.
    sample=(u*7.0)%24;a=int(sample);f=sample-a
    tex=(native[a]*(1-f)+native[(a+1)%24]*f).permute(2,0,1)[None]
    col=torch.zeros_like(pos).new_zeros((len(pos),3))
    for offset in [0.,.5]:
        cycle=torch.remainder(data['texphase']+offset-u*.38,1.)
        tex_y=155+cycle*142
        tex_grid=torch.stack([uv[:,0]/263*2-1,tex_y/319*2-1],dim=-1)[None,None]
        piece=F.grid_sample(tex,tex_grid,align_corners=True,padding_mode='zeros')[0,:,0].T
        col+=piece*(torch.sin(cycle*math.pi).square())[:,None]
    col*=data['tip'][:,None]
    ignition=min(1.,max(0.,u/.20))
    cooling=math.exp(-max(0.,u-3.0)*1.0)
    col=col*ignition*cooling
    pixel=torch.stack([pos[:,0]*scale+W*.5,H*.52-pos[:,1]*scale],dim=-1)
    ij=torch.floor(pixel).long();frac=pixel-ij
    canvas=torch.zeros((4,H*W),device=device)
    payload=torch.cat([col,torch.ones_like(col[:,:1])],dim=1)*area[:,None]
    for dx,dy in [(0,0),(1,0),(0,1),(1,1)]:
        x=ij[:,0]+dx;y=ij[:,1]+dy
        valid=(x>=0)&(x<W)&(y>=0)&(y<H)
        weight=(frac[:,0] if dx else 1-frac[:,0])*(frac[:,1] if dy else 1-frac[:,1])
        idx=(y*W+x).clamp(0,H*W-1)
        canvas.scatter_add_(1,idx[None].expand(4,-1),(payload*(weight*valid)[:,None]).T)
    canvas=canvas.view(1,4,H,W)
    # Subpixel footprint and optical bloom, in linear light.
    canvas=F.avg_pool2d(canvas,3,stride=1,padding=1)
    rgb=canvas[:,:3]/(1+canvas[:,3:]*.32)
    glow=F.avg_pool2d(F.avg_pool2d(rgb,19,stride=1,padding=9),19,stride=1,padding=9)
    rgb=(rgb+glow*.20)*1.25
    fade=min(1.,max(0.,(SECONDS-frame/FPS)/.5))
    rgb*=fade
    im=((rgb*(2.51*rgb+.03))/(rgb*(2.43*rgb+.59)+.14)).clamp(0,1)
    im=torch.where(im<=.0031308,im*12.92,1.055*im.pow(1/2.4)-.055)
    pixels=(im[0].permute(1,2,0)*255).byte().cpu().numpy()
    encoder.stdin.write(pixels.tobytes())
    if frame%6==0 or frame==round(SECONDS*FPS)-1:
        im=Image.fromarray(pixels);im.thumbnail((1280,720));im.save(OUT/f'{frame:04d}.jpg',quality=93)

for frame in range(round(SECONDS*FPS)):
    u=float(clock(frame/FPS));advance(u,u-prev);prev=u
    image(u,frame)
    if frame%30==0:
        if not torch.isfinite(pos).all():raise RuntimeError('Invalid trajectory')
        row={'frame':frame,'time':frame/FPS,'flowTime':u,'speed':float(vel.norm(dim=1).mean()),'distanceToWord':float((pos-target).norm(dim=1).mean()),'elapsed':round(time.monotonic()-started,1),'gpuMiB':round(torch.cuda.max_memory_allocated()/1048576)}
        checks.append(row);print(json.dumps(row),flush=True)
encoder.stdin.close();assert encoder.wait()==0
(ROOT/'mass-report.json').write_text(json.dumps({'frames':round(SECONDS*FPS),'fps':FPS,'dimensions':[W,H],'parcels':len(pos),'source':'24 native flame radiance frames from flame-native-emitter','method':'VFX cached-fire parcel transport with finite arrival force and free release; not coupled CFD','checks':checks},indent=2))
print(str(video),flush=True)
