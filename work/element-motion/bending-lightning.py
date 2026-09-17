"""CPU-rendered, art-directed branching electrical discharge on the shared source path.

This is a procedural VFX channel model, not an electrodynamics solver. Channel
geometry persists across return strokes. The source choreography is shared with
the fluid and rigid-body studies; radiance and branching are material-specific.
"""
import sys, json, math, subprocess, time
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from shared_motion import pose, DATA

R=Path(__file__).resolve().parent
O=R.parent.parent/'outputs/cybrdelic-type/elements/motion/bending'
OUT=R/'bending-rebuild/lightning-frames'; OUT.mkdir(exist_ok=True)
cv2.setNumThreads(2)
W,H,SS,FPS=1920,1080,2,30
WW,HH=W*SS,H*SS
PILOT='--pilot' in sys.argv
rng=np.random.default_rng(6935)
times=np.linspace(.08,1.68,241)
center=np.array([pose(t)[0] for t in times])
tangent=np.array([pose(t)[1] for t in times])
normal=np.column_stack((-tangent[:,1],tangent[:,0]))

def jitter_curve(points, seed, amplitude):
    local=np.random.default_rng(seed)
    pts=points.copy()
    # Independent scales, with a diminishing high-frequency displacement.
    u=np.linspace(0,1,len(pts))
    for frequency,gain in [(23,1),(53,.48),(113,.2),(191,.08)]:
        samples=local.normal(size=(frequency,2))
        offset=np.column_stack([np.interp(u,np.linspace(0,1,frequency),samples[:,j]) for j in range(2)])
        pts+=offset*amplitude*gain
    return pts

channels=[jitter_curve(center,8000+j,.085) for j in range(9)]
branches=[]
for k in range(9):
    local=np.random.default_rng(330+k)
    network=[]
    # Irregularly distributed branching sites, including sparse quiet intervals.
    sites=np.sort(local.choice(np.arange(7,233),size=43,replace=False))
    for site in sites:
        side=local.choice([-1,1]); length=min(.95,.13*(1-local.random())**(-.57))
        direction=tangent[site]*local.uniform(.1,.8)+normal[site]*side*local.uniform(.7,1.2)
        direction/=np.linalg.norm(direction)
        n=max(9,int(length*110));u=np.linspace(0,1,n)
        points=channels[k][site]+u[:,None]*direction*length
        points=jitter_curve(points,int(local.integers(1,1_000_000)),length*.075)
        points+=np.sin(u*math.pi)[:,None]*normal[site]*side*length*.13
        points[0]=channels[k][site]
        strength=local.uniform(.3,.8)
        network.append((site,points,strength))
        if length>.18:
            split=int(n*local.uniform(.35,.65)); start=points[split]
            subdir=direction+normal[site]*side*local.uniform(.65,1.2)
            subdir/=np.linalg.norm(subdir)
            sub=jitter_curve(start+np.linspace(0,1,13)[:,None]*subdir*length*.48,int(local.integers(1,1_000_000)),length*.045)
            sub[0]=start;network.append((site,sub,strength*.32))
    branches.append(network)

def project(points):
    return np.column_stack(((points[:,0]/10.5+.5)*WW,(.5-(points[:,1]-1.903125)/5.90625)*HH)).astype(np.int32)

def render(frame):
    t=(frame+.5)/FPS
    field=np.zeros((HH,WW),np.float32)
    if .08<t<2.26:
        end=min(t,1.68)
        # Restrikes follow established channels. The six-frame cycle is
        # modulated to avoid a metronomic flash or a continuous neon tube.
        phase=max(0,t-.08)
        discharge=int(phase/.087)
        age=phase-discharge*.087
        strength=(.45+.55*np.sin(discharge*2.399)**2)*np.exp(-age/.027)
        if t>1.72:
            strength*=math.exp(-(t-1.72)*9)
        ch=discharge//3%len(channels)
        pts=channels[ch]
        active=np.where((times<=end)&(times>max(.08,end-.92)))[0]
        if len(active)>1:
            pixel=project(pts)
            for a,b in zip(active[:-1],active[1:]):
                source_age=end-times[a]
                energy=strength*(.3+.7*math.exp(-source_age*1.8))
                cv2.line(field,tuple(pixel[a]),tuple(pixel[b]),float(9*energy),3,cv2.LINE_AA)
            for site,branch,weight in branches[ch]:
                if site not in active:continue
                bp=project(branch)
                for j in range(len(bp)-1):
                    taper=(1-j/len(bp))**.75
                    cv2.line(field,tuple(bp[j]),tuple(bp[j+1]),float(7*strength*weight*taper),2 if j<len(bp)*.45 else 1,cv2.LINE_AA)
    core=cv2.resize(field,(W,H),interpolation=cv2.INTER_AREA)
    near=cv2.GaussianBlur(core,(0,0),1.4)
    corona=cv2.GaussianBlur(core,(0,0),5.4)
    halo=cv2.GaussianBlur(core,(0,0),18)
    linear=core[:,:,None]*np.array([1,.98,1.0])+near[:,:,None]*np.array([.18,.32,.74])+corona[:,:,None]*np.array([.38,.64,1.35])+halo[:,:,None]*np.array([.15,.29,.8])
    rgb=1-np.exp(-linear)
    rgb=np.where(rgb<=.0031308,rgb*12.92,1.055*np.maximum(rgb,0)**(1/2.4)-.055)
    return (np.clip(rgb,0,1)*255+.5).astype(np.uint8)

start=time.time()
frames=[20,41,50,68] if PILOT else range(120)
encoder=None
if not PILOT:
    encoder=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-crf','16','-preset','slow','-pix_fmt','yuv420p','-movflags','+faststart',str(O/'lightning.mp4')],stdin=subprocess.PIPE)
for f in frames:
    pixels=render(f)
    if encoder:encoder.stdin.write(pixels.tobytes())
    if PILOT or f%10==0:Image.fromarray(pixels).resize((1280,720),Image.Resampling.LANCZOS).save(OUT/f'{f:04}.jpg',quality=95)
    if f%30==0:print('FRAME',f,round(time.time()-start,1),flush=True)
if encoder:
    encoder.stdin.close()
    if encoder.wait()!=0:raise RuntimeError('Encoding failed')
(R/'bending-rebuild/lightning-report.json').write_text(json.dumps({'renderer':'CPU supersampled linear-light channel rasterization','model':'Procedural branched discharge VFX; not full electrodynamics','seed':6935,'frames':len(frames),'fps':FPS,'size':[W,H],'elapsed':time.time()-start,'trail':'shared-trail.json'},indent=2))
print('LIGHTNING COMPLETE',flush=True)
