from pathlib import Path
root=Path(__file__).resolve().parent
code=(root/'render_mass.py').read_text()
code=code.replace('import os, json, time, math, subprocess','import os, json, time, math, subprocess, gzip')
code=code.replace("device='cuda'", "device=os.environ.get('FIRE_DEVICE','cuda')")
start=code.index('N_S=640;N_V=64')
end=code.index('def advance(u,delta):')
code=code[:start]+'''
base=Path(r'C:\\Users\\alexf\\Documents\\Codex\\2026-09-04\\re\\work\\cybrdelic.github.io\\assets\\gallery\\spatial')
info=json.loads((base/'flame-native-emitter/index.json').read_text())
shape=tuple(info['dimensions'][::-1]);h=np.array(info['extent'])/(np.array(info['dimensions'])-1)
raw=np.frombuffer(gzip.decompress((base/info['frames'][0]['file']).read_bytes()),np.uint8).reshape(*shape,4)
rgba=(raw.astype(np.float32)/255)**2*16
sigma=rgba[...,3];atten=np.exp(-sigma*h[1]);trans=np.concatenate([np.ones_like(atten[:,:1]),np.cumprod(atten[:,:-1],axis=1)],axis=1)
energy=trans[...,None]*rgba[...,:3]*(1-atten[...,None])/np.maximum(sigma[...,None],1e-6)
energy*=np.clip((np.arange(shape[0])[:,None,None,None]-10)/35,0,1)**2
energy*=np.clip((rgba[...,:1]-rgba[...,2:3])/(rgba[...,:1]+1e-6),0,1)**2
lum=energy.max(axis=-1);prob=lum.ravel()/lum.sum()
N=100000
idx=rng.choice(prob.size,N,p=prob)
zi,yi,xi=np.unravel_index(idx,shape)
source_pos=np.stack([xi*h[0],yi*h[1],zi*h[2]],axis=-1)
source_pos[:,0]-=np.average(source_pos[:,0]);source_pos[:,1]-=np.average(source_pos[:,1])
colors=energy.reshape(-1,3)[idx]/np.maximum(lum.ravel()[idx,None],1e-8)
# Monotone material coordinates keep neighbouring parcels related; they do not
# become a raster stencil or a persistent channel in the simulation.
order=np.argsort(source_pos[:,2]+rng.normal(0,.012,N));s=np.empty(N);s[order]=(np.arange(N)+.5)/N
native_s=(source_pos[:,2]-source_pos[:,2].min())/(source_pos[:,2].max()-source_pos[:,2].min())
s=s*.68+native_s*.32
sx=source_pos[:,0]
bins=np.minimum(63,(s*64).astype(int))
mean=np.bincount(bins,weights=sx,minlength=64)/np.maximum(1,np.bincount(bins,minlength=64))
cross=(sx-mean[bins]*.5)*.35
cross+=rng.normal(0,.006,N)
data={k:[] for k in ['target','initial','end_v','color','area','phase']}
for j,curve in enumerate(curves):
    p=curve['points'].copy();p[:,1]-=1.95
    d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    closed=np.linalg.norm(p[-1]-p[0])<.02
    along=np.remainder(s+(np.arange(N)%2)*.5,1.) if closed else s
    center=np.stack([np.interp(along*d[-1],d,p[:,k]) for k in range(2)],axis=-1)
    tangents=curve['tangent']
    tangent=np.stack([np.interp(along*d[-1],d,tangents[:,k]) for k in range(2)],axis=-1)
    normal=np.stack([-tangent[:,1],tangent[:,0]],axis=-1)
    target=np.c_[center+normal*cross[:,None],source_pos[:,1]*.18]
    # Actual spatial samples from the source volume form the incoming fire mass.
    initial=np.c_[source_pos[:,2]*.80-5.1,source_pos[:,0]*.80+.10,source_pos[:,1]*.80]
    initial+=rng.normal(0,.012,initial.shape)
    end=np.c_[tangent*.56+normal*(.18*np.sin(s*25+j))[:,None],np.zeros(N)]
    end+=rng.normal(0,.12,end.shape)
    data['target'].append(target);data['initial'].append(initial);data['end_v'].append(end)
    taper=np.ones(N) if closed else np.minimum(1,s/.065)*np.minimum(1,np.maximum(0,(.98-s))/.085)
    data['color'].append(colors*taper[:,None]);data['phase'].append(s*15+j*.7)
    data['area'].append(np.full(N,d[-1]/2*(W/1280)**2*.080*(32000/N)))
del raw,rgba,sigma,atten,trans,energy,lum,prob
def tensor(v):return torch.tensor(v,dtype=torch.float32,device=device)
data={k:tensor(np.concatenate(v)) for k,v in data.items()}
pos=data['initial'].clone();vel=torch.zeros_like(pos);vel[:,0]=2.2
target=data['target'];endv=data['end_v'];phase=data['phase'];area=data['area']
T=2.65
clock=PchipInterpolator([0,1.7,2.6,3.8,5.2,6.5],[0,2.12,2.50,2.78,4.25,5.60])
prev=0.;started=time.monotonic();checks=[]
video=ROOT.parent/'outputs'/'cybrdelic-fire-momentum.mp4'
encoder=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],stdin=subprocess.PIPE)

''' +code[end:]
code=code.replace("torch.cos(q[:,0]*4-now*2+phase*.1)],dim=1)","torch.cos(q[:,0]*4-now*2+phase*.1),torch.sin(q[:,0]*3+q[:,1]*4-now*3)],dim=1)")
code=code.replace("tensor([1.65,1.05])","tensor([1.65,1.05,0.])")
start=code.index('    # Interpolate actual cached fire frames;')
end=code.index('    ignition=',start)
code=code[:start]+'''    col=data['color']*(.85+.15*torch.sin(phase+u*4))[:,None]
'''+code[end:]
code=code.replace("cooling=math.exp(-max(0.,u-3.0)*1.0)","cooling=math.exp(-max(0.,u-2.9)*.9)")
code=code.replace("rgb=(rgb+glow*.20)*1.25","rgb=(rgb+glow*.20)*1.15")
code=code.replace("glow=F.avg_pool2d(F.avg_pool2d(rgb,19,stride=1,padding=9),19,stride=1,padding=9)", "glow=rgb\n    for _ in range(2):\n        glow=F.avg_pool2d(F.avg_pool2d(glow,(1,19),stride=1,padding=(0,9)),(19,1),stride=1,padding=(9,0))")
code=code.replace("'source':'24 native flame radiance frames from flame-native-emitter'","'source':'Spatial emission samples from native flame-native-emitter 3D cache'")
code=code.replace("'VFX cached-fire parcel transport with finite arrival force and free release; not coupled CFD'","'3D cached-fire emission parcels; finite arrival force followed by free turbulent release; not coupled CFD'")
(root/'render_cloud.py').write_text(code)
print(root/'render_cloud.py')
