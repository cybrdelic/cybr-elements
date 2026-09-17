"""Offline 3-D reactive-flow look-development, never executed by the website.

Projected incompressible velocity, limited MacCormack scalar transport,
fuel/oxidizer reaction, cooling, buoyancy and a spatial wind force. This is a
graphics combustion model, not a calibrated engineering combustion solver.
There is deliberately NO frame fit, reverse playback, or fabricated loop.
Only rendered previews and summary metadata are retained to bound disk use.
"""
import argparse, gzip, json, math, os, shutil, time
from functools import lru_cache
from pathlib import Path
os.environ.setdefault('OMP_NUM_THREADS', '2')
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('--pilot',action='store_true')
p.add_argument('--name', default='reactive-fire-pilot')
p.add_argument('--size', type=int, nargs=3, default=[128, 80, 160], help='x y z cells')
p.add_argument('--seconds', type=float, default=8)
p.add_argument('--warmup', type=float, default=4)
p.add_argument('--fps', type=int, default=24)
p.add_argument('--substeps', type=int, default=3)
p.add_argument('--wind', type=float, default=0)
p.add_argument('--control', choices=['none','directed','orbit','choreographed'], default='none')
p.add_argument('--move', choices=['sweep','whip','helix','figure-eight','suite'], default='sweep')
p.add_argument('--gesture-version', choices=['19','20','20b','21','21b','22','22b','23'], default='19')
p.add_argument('--padded-domain',action='store_true',help='Expand bounds with cell count; preserve production voxel spacing')
p.add_argument('--orbit-period', type=float, default=5.)
p.add_argument('--control-strength', type=float, default=1)
p.add_argument('--pulse', action='store_true')
p.add_argument('--pulse-duration', type=float, default=2.85)
p.add_argument('--save-every', type=int, default=1)
p.add_argument('--resume', action='store_true')
p.add_argument('--checkpoint-every', type=float, default=2)
a = p.parse_args()
if a.gesture_version=='23':
    from bending_fire_cast_v23 import pose as gesture_pose
elif a.gesture_version=='22b':
    from bending_fire_moves_v22b import pose as gesture_pose,turn_rate
elif a.gesture_version=='22':
    from bending_fire_moves_v22 import pose as gesture_pose
elif a.gesture_version=='21b':
    from bending_fire_choreography_v21b import pose as gesture_pose, FlowGuide, strength as guide_strength
elif a.gesture_version=='21':
    from bending_fire_choreography_v21 import pose as gesture_pose, FlowGuide, strength as guide_strength
elif a.gesture_version.startswith('20'):
    from bending_fire_moves_v20 import pose as gesture_pose
else:
    gesture_pose=None
from sigil_native_motion import pose as nozzle_pose, turn_rate as nozzle_turn, WRITE, START, MODE
if not a.name.replace('-', '').isalnum(): raise ValueError('Expected a local artifact name')
out = ROOT/'sigil-native/fire-c'
out.mkdir(parents=True,exist_ok=True)
if (out/'complete.json').exists() and not a.resume: raise RuntimeError('Completed bake exists; use a new name')
if shutil.disk_usage(out).free < 1024**3: raise RuntimeError('1 GiB streaming render reserve required')
if not torch.cuda.is_available(): raise RuntimeError('CUDA is required for this offline bake')
torch.set_num_threads(2)
torch.set_grad_enabled(False)
device='cuda'
X,Y,Z=a.size
shape=(Z,Y,X)
# Match the gallery field's fixed world-space coordinate contract. No per-frame fit.
lo=np.array([-5.25,-3. if MODE=='word' else -.6,0],np.float32)
extent=np.array([10.5,6. if MODE=='word' else 1.2,4.2],np.float32)
velocity_size=np.array([66,38,64])
if a.padded_domain:
    if np.any(np.array(a.size)<[264,152,320]):raise ValueError('Padded domain cannot lower production resolution')
    expanded=extent*(np.array(a.size)-1)/(np.array([264,152,320])-1)
    lo[:2]-=(expanded[:2]-extent[:2])*.5
    extent=expanded.astype(np.float32)
    velocity_size=np.ceil(velocity_size*np.array(a.size)/[264,152,320]).astype(int)
h=torch.tensor(extent/(np.array(a.size)-1),device=device)
zz,yy,xx=torch.meshgrid(*(torch.linspace(-1,1,n,device=device) for n in shape),indexing='ij')
grid=torch.stack([xx,yy,zz],dim=-1)[None]
x=lo[0]+(xx+1)*float(extent[0])*.5
y=lo[1]+(yy+1)*float(extent[1])*.5
z=lo[2]+(zz+1)*float(extent[2])*.5
step_scale=(2/torch.tensor(extent,device=device)).view(1,3,1,1,1)
state=torch.zeros((1,8,*shape),device=device)
# Channels: velocity xyz, fuel, oxygen, temperature, soot, reaction-rate.
state[:,4]=1
edge=torch.minimum(torch.minimum(1-xx.abs(),1-yy.abs()),1-zz.abs()).clamp(0,1)
sponge=(edge/.10).clamp(0,1)[None,None]
source=torch.exp(-((x/.32)**4+(y/.245)**4+((z-.34)/.075)**4))
source=(source>.01)*source
if a.gesture_version=='22b':turn_support=torch.exp(-((((x-.8)**2+y*y).sqrt()/1.5)**4+((z-1.)/2.)**4))
frequency=[torch.fft.fftfreq(n,device=device) for n in shape[:2]]+[torch.fft.rfftfreq(X,device=device)]
kz,ky,kx=torch.meshgrid(*frequency,indexing='ij')
# Compatible central-difference Fourier symbols: projection removes precisely
# the divergence subsequently measured by central differences.
k=torch.stack([torch.sin(2*math.pi*kx)/h[0],torch.sin(2*math.pi*ky)/h[1],torch.sin(2*math.pi*kz)/h[2]])
k2=(k*k).sum(0).clamp_min(1e-12)
dt=1/(a.fps*a.substeps)
rows=[]; started=time.monotonic(); before_projection=[]; after_projection=[]
if a.gesture_version.startswith('21'):
    controller=FlowGuide(lo,extent,np.array(a.size)//4)
    @lru_cache(maxsize=3)
    def control_frame(index):return torch.from_numpy(controller.frame(index)).to(device)

def steer_broad_flow(v,t,temp,soot):
    if guide_strength(t)<1e-6:return
    phase=t*24;index=int(phase);fraction=phase-index
    guide=control_frame(index)*(1-fraction)+control_frame(index+1)*fraction
    low=F.interpolate(v[None],size=controller.shape,mode='trilinear',align_corners=True)[0]
    force=(guide[:3]-low)*(5.5*guide[3:4])
    force*=torch.clamp(35/torch.linalg.vector_norm(force,dim=0).clamp_min(1e-6),max=1)[None]
    guide[:3]=force
    applied=F.interpolate(guide[None],size=shape,mode='trilinear',align_corners=True)[0]
    # Add a broad external control force. Fine-scale velocity is not damped to
    # the guide: native turbulent residuals and combustion remain in the solve.
    v.add_(applied[:3]*dt)
    v[2].sub_((temp*3.4-soot*.32)*applied[3]*dt)

def advect(q,vel,sign=1):
    lookup=grid-(vel*step_scale*dt*sign).permute(0,2,3,4,1)
    return F.grid_sample(q,lookup,mode='bilinear',padding_mode='border',align_corners=True)

def derivative(q,axis,spacing):
    return (torch.roll(q,-1,axis)-torch.roll(q,1,axis))/(2*spacing)

def divergence(v):
    return derivative(v[0,0],2,h[0])+derivative(v[0,1],1,h[1])+derivative(v[0,2],0,h[2])

def step(t):
    global state
    vel=state[:,:3]
    moved=advect(state,vel)
    # Correct scalar diffusion, constrained to the source neighbourhood's range.
    returned=advect(moved,vel,-1)
    corrected=moved[:,3:]+.5*(state[:,3:]-returned[:,3:])
    upper=F.max_pool3d(state[:,3:],3,stride=1,padding=1)
    lower=-F.max_pool3d(-state[:,3:],3,stride=1,padding=1)
    # The limiter belongs to the departure neighbourhood, not the destination
    # cell. Clamping against the latter pinned fast jets to a one-cell front
    # and generated axis-aligned cuts whenever velocity exceeded one cell/dt.
    departure=grid-(vel*step_scale*dt).permute(0,2,3,4,1)
    upper=F.grid_sample(upper,departure,mode='nearest',padding_mode='border',align_corners=True)
    lower=F.grid_sample(lower,departure,mode='nearest',padding_mode='border',align_corners=True)
    moved[:,3:]=torch.maximum(lower,torch.minimum(upper,corrected)).clamp_min_(0)
    state=moved
    # These correction buffers are dead after the scalar update. Keeping them
    # alive through steering, vorticity and FFT projection retained gigabytes
    # of scratch storage without changing a single numerical result.
    del vel,returned,corrected,upper,lower,departure,moved
    fuel,oxygen,temp,soot=[state[0,c] for c in [3,4,5,6]]
    # Only a spherical moving nozzle adds fuel; its reacting wake is free.
    center,direction,on,speed=nozzle_pose(t)
    cx,cz=center;dx,dz=direction
    px=x-float(cx);pz=z-float(cz)
    across=-px*float(dz)+pz*float(dx);along=px*float(dx)+pz*float(dz)
    nozzle=torch.exp(-((across/.23)**2+((y-.08*math.sin(t*17)-across*.35*math.sin(t*11))/.045)**2+(along/.12)**2)*1.5)
    if MODE=='word':nozzle=torch.exp(-((px/.080)**2+((y+2.)/.100)**2+(pz/.080)**2)*1.5)
    inject=(nozzle*on*dt*(20+speed*3)*(0.72+0.28*math.sin(t*47))).clamp(0,1)
    fuel.lerp_(torch.ones_like(fuel)*.95,inject)
    oxygen.mul_(1-inject)
    temp.lerp_(torch.ones_like(temp)*1.25,inject)
    v=state[0,:3]
    wake=torch.exp(-((across/.32)**2+(y/.3)**2+(along/.55)**2))*on
    v[2].add_(wake*torch.sin(y*18+t*15)*20*dt)
    v[1].add_(wake*torch.cos(pz*14-t*12)*16*dt)
    shear=4.8*torch.sin(y*19+t*13)*torch.cos((px+pz)*12-t*11)
    if MODE=='arc':
        v[0].lerp_(float(dx)*8.0+shear*float(-dz),inject)
        v[1].lerp_(torch.sin(px*38+pz*27+t*23)*.8,inject)
        v[2].lerp_(float(dz)*8.0+shear*float(dx),inject)
    else:
        v[0].lerp_(shear*.35,inject)
        v[1].lerp_(torch.ones_like(y)*3.5+shear*.3,inject)
        v[2].lerp_(shear*.3,inject)
    activation=((temp-.15)/.22).clamp(0,1)
    burn=torch.minimum(fuel,oxygen*.7)*(1-math.exp(-8*dt))*activation
    fuel.sub_(burn); oxygen.sub_(burn/ .7).clamp_(0,1)
    temp.add_(burn*5.5).mul_(math.exp(-1.15*dt)).clamp_(0,3)
    soot.add_(burn*.8).mul_(math.exp(-1.15*dt))
    # A luminous reaction front; hot unburnt fuel is not an opaque yellow blob.
    state[0,7]=burn/dt
    del burn,activation
    v[2].add_((temp*3.4-soot*.32)*dt)
    v[0].add_((a.wind*(z-.25).clamp(0,2)*((z-.25)/.5).clamp(0,1))*dt)
    if a.control=='choreographed' and a.gesture_version.startswith('21'):steer_broad_flow(v,t,temp,soot)
    if a.gesture_version=='22b':
        # Exact integration of a perpendicular turning force. It preserves
        # horizontal speed before projection; no radius, curve, velocity target
        # or scalar field is fitted. Buoyant vertical motion remains untouched.
        angle=turn_support*(turn_rate(t)*dt);c=angle.cos();s=angle.sin();old_x=v[0].clone()
        v[0].mul_(c).sub_(v[1]*s);v[1].mul_(c).add_(old_x*s)
        del angle,c,s,old_x
    if a.control=='directed':
        dx=x-(.65+.12*math.sin(t*.8));dz=(z-2.15)*.90
        radius=(dx*dx+dz*dz).sqrt().clamp_min(.05)
        control=torch.exp(-((radius-1.4)/1.2)**4-(y/.82)**4)*a.control_strength
        omega=2.5+.45*math.sin(t*1.4)
        radial=(radius-(1.4+.13*math.sin(t*1.9)))*3.2
        desired_x=-omega*dz-radial*dx/radius
        desired_z=(omega*dx-radial*dz/radius)/.90+.18
        # Pressure projection below resolves this authored steering force;
        # hot gas still advects, mixes, reacts and sheds native vortices.
        # Authored manipulation counters buoyancy locally. Without this force,
        # the burning jet rises out of the circulation into the finite domain.
        v[2].sub_((temp*3.4-soot*.32)*control*dt)
        guide=(control*(1-math.exp(-5.5*dt))).clamp(0,1)
        v[0].lerp_(desired_x,guide);v[1].lerp_(-y*.9+.22*torch.sin(z*2.5+t*2),guide);v[2].lerp_(desired_z,guide)
    # Turn the hot gas momentum, preserving speed before pressure projection.
    # Native buoyancy, scalar transport and combustion remain active.
    angle=(temp*.8+soot*4).clamp(0,1)*(float(nozzle_turn(t))*dt*.35 if MODE=='arc' else 0.)
    c=angle.cos();s=angle.sin();old_x=v[0].clone()
    v[0].mul_(c).sub_(v[2]*s);v[2].mul_(c).add_(old_x*s)
    del angle,c,s,old_x
    if MODE=='word':
        lift=max(0.,min(1.,(START+WRITE+.35-t)/.20))*.65
        v[2].sub_((temp*3.4-soot*.32)*(lift*dt))
    # Resolved vorticity confinement retains rolled shear structures.
    wx=derivative(v[2],1,h[1])-derivative(v[1],0,h[2])
    wy=derivative(v[0],0,h[2])-derivative(v[2],2,h[0])
    wz=derivative(v[1],2,h[0])-derivative(v[0],1,h[1])
    omega=torch.stack([wx,wy,wz]); magnitude=torch.linalg.vector_norm(omega,dim=0)
    grad=torch.stack([derivative(magnitude,2,h[0]),derivative(magnitude,1,h[1]),derivative(magnitude,0,h[2])])
    grad=grad/torch.linalg.vector_norm(grad,dim=0).clamp_min(1e-6)
    v.add_(torch.linalg.cross(grad,omega,dim=0)*(.12*dt))
    del wx,wy,wz,omega,magnitude,grad
    v.mul_(sponge[0])
    spectral=torch.fft.rfftn(v,dim=(-3,-2,-1))
    projection=(spectral*k).sum(0)/k2
    spectral-=k*projection
    # Small physical/numerical viscosity, not a temporal image filter.
    spectral*=torch.exp(-k2*(.000025*dt))
    v.copy_(torch.fft.irfftn(spectral,s=shape,dim=(-3,-2,-1)))
    state[:,3:4].mul_(sponge)
    state[:,5:].mul_(sponge)
    oxygen.lerp_(torch.ones_like(oxygen),1-sponge[0,0])
    return float(divergence(state[:,:3]).square().mean().sqrt())

def radiance():
    temp=state[0,5]; soot=state[0,6]; reaction=state[0,7]
    hot=((temp-.28)/1.8).clamp(0,1)
    sigma=(soot*4.4+reaction*.025).clamp(0,16)
    tau=torch.flip(torch.cumsum(torch.flip(soot,[0]),dim=0),[0])*h[2]*4.4
    key=torch.exp(-tau)
    # Temperature controls hue; resolved reaction controls luminous structure.
    colors=torch.stack([torch.ones_like(hot),.035+.93*hot.pow(1.3),.002+.72*hot.pow(3.0)],dim=-1)
    front=reaction.clamp_min(0).pow(.95)
    emission=colors*(front*6.5)[...,None]
    light=torch.tensor([.020,.019,.025],device=device)+key[...,None]*torch.tensor([1.4,1.10,.85],device=device)
    rgb=emission+soot[...,None]*4.4*.42*light/(4*math.pi)
    return rgb,sigma

def capture(frame,t,div):
    rgb,sigma=radiance()
    packed=torch.cat([(rgb/16).clamp(0,1).sqrt(),(sigma/16).sqrt()[...,None]],dim=-1)
    raw=(packed*255).round().to(torch.uint8).cpu().numpy()
    (out/f'{frame:04}.rgba.gz').write_bytes(gzip.compress(raw.tobytes(),compresslevel=2))
    # Native solver velocity, in metres/second, for later temporal reconstruction.
    velocity=F.interpolate(state[:,:3],size=tuple(int(n) for n in velocity_size[::-1]),mode='trilinear',align_corners=True)[0].permute(1,2,3,0).cpu().numpy().astype('<f2')
    np.save(out/f'{frame:04}.velocity.npy',velocity)
    atten=torch.exp(-sigma*h[1]); transmission=torch.cat([torch.ones_like(atten[:,:1]),torch.cumprod(atten[:,:-1],dim=1)],dim=1)
    image=(transmission[...,None]*rgb*(1-atten[...,None])/sigma[...,None].clamp_min(1e-6)).sum(1)
    image=((image*(2.51*image+.03))/(image*(2.43*image+.59)+.14)).clamp(0,1)
    image=torch.where(image<=.0031308,image*12.92,1.055*image.pow(1/2.4)-.055)
    pixels=(image.flip(0)*255).byte().cpu().numpy()
    im=Image.fromarray(pixels).resize((396,480))
    im.save(out/f'{frame:04}.jpg',quality=90)
    row={'frame':frame,'time':t,'fuel':float(state[0,3].sum()),'soot':float(state[0,6].sum()),'reaction':float(state[0,7].sum()),'divergenceRMS':div,'activeVoxels':int(np.any(raw>0,axis=-1).sum()),'seconds':round(time.monotonic()-started,2)}
    rows.append(row)
    if frame%a.fps==0: print(json.dumps(row),flush=True)


import subprocess
import sys
FPS=30
SIM_FPS=a.fps
DURATION=4.0
TOTAL=72 if a.pilot else round(DURATION*FPS)
W,H=1920,1080
video=ROOT/'sigil-native/fire-c.mp4'
video=video.with_name(video.stem+'-pilot.mp4') if a.pilot else video
video.parent.mkdir(exist_ok=True)
encoder=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],stdin=subprocess.PIPE)
def render(frame):
    rgb,sigma=radiance()
    atten=torch.exp(-sigma*h[1])
    transmission=torch.cat([torch.ones_like(atten[:,:1]),torch.cumprod(atten[:,:-1],dim=1)],dim=1)
    linear=(transmission[...,None]*rgb*(1-atten[...,None])/sigma[...,None].clamp_min(1e-6)).sum(1)
    # Upsample the volume integration in linear light, then optical glow.
    linear=F.interpolate(linear.permute(2,0,1).flip(1)[None],size=(768,1920),mode='bicubic',align_corners=False).clamp_min(0)
    blur=F.avg_pool2d(F.avg_pool2d(linear,(1,21),stride=1,padding=(0,10)),(21,1),stride=1,padding=(10,0))
    linear=(linear+blur*.018)*.72
    linear=F.pad(linear,(0,0,120,192))
    # No image fade: the gas evolves and dissipates under the model.
    fade=1.
    linear=linear*fade
    im=((linear*(2.51*linear+.03))/(linear*(2.43*linear+.59)+.14)).clamp(0,1)
    im=torch.where(im<=.0031308,im*12.92,1.055*im.pow(1/2.4)-.055)
    pixels=(im[0].permute(1,2,0)*255).byte().cpu().numpy()
    encoder.stdin.write(pixels.tobytes())
    if frame%5==0 or frame==TOTAL-1:
        Image.fromarray(pixels).resize((1280,720),Image.Resampling.LANCZOS).save(out/f'{frame:04}.jpg',quality=91)
for frame in range(TOTAL):
    for sub in range(a.substeps):div=step((frame+sub/a.substeps)/SIM_FPS)
    if frame%FPS==0:
        if not torch.isfinite(state).all():raise RuntimeError('Nonfinite state')
        if torch.cuda.max_memory_allocated()>6.8*1024**3:raise RuntimeError('GPU memory budget exceeded')
        print(json.dumps({'frame':frame,'total':TOTAL,'elapsed':round(time.monotonic()-started,1),'gpuMiB':round(torch.cuda.max_memory_allocated()/1048576),'divergence':div}),flush=True)
    render(frame)
encoder.stdin.close()
if encoder.wait()!=0:raise RuntimeError('Encoding failed')
(ROOT/'sigil-native/fire-c-report.json').write_text(json.dumps({'frames':TOTAL,'fps':FPS,'size':[W,H],'solverGrid':a.size,'elapsed':time.monotonic()-started,'peakGpuMiB':torch.cuda.max_memory_allocated()/1048576,'source':'bake-reactive-fire.py','changes':'Single moving fuel nozzle with backward jet momentum; speed-preserving hot-gas turning; native buoyancy, reaction, pressure and radiance; no trail fitting, morph or cached particles.'},indent=2))
print(str(video),flush=True)
