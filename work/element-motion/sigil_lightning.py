"""Art-directed electrical sigil: persistent 3D channel trees, return-stroke
exposure and a diffusing/recombining corona field. Not a plasma simulation.
The corona is a simulated luminous field; no white wordmark is composited.
"""
from pathlib import Path
import os,sys,time,json,subprocess
os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
import numpy as np,cv2
from scipy.ndimage import gaussian_filter,gaussian_filter1d,map_coordinates
from PIL import Image
R=Path(__file__).resolve().parent;B=R/'sigil-v1';variant=sys.argv[1];assert variant in ['01','02']
O=B/f'lightning-{variant}';O.mkdir(exist_ok=True);cv2.setNumThreads(2)
D=np.load(B/f'mark-{variant}.npz');W,H=1920,1080;rng=np.random.default_rng(9301+int(variant))
mask=cv2.resize(D['mask'].astype('f'),(640,360));arrival=cv2.resize(D['arrival'],(640,360));sdf=D['sdf']
yy,xx=np.indices(mask.shape,dtype=np.float32);charge=np.zeros_like(mask);rows=[]
points=D['points'];times=D['times'];emit=D['emit'];splits=np.flatnonzero((emit[1:]==0)|(emit[:-1]==0)|(np.linalg.norm(np.diff(points,axis=0),axis=1)>.10))+1
paths=[]
for ids in np.split(np.arange(len(points)),splits):
 if len(ids)<3 or not np.all(emit[ids]):continue
 ids=ids[::2];p=points[ids];t=times[ids]
 if len(p)<2:continue
 # Fixed, smoothly perturbed channel geometry; repeated strokes reuse it.
 for layer in range(3):
  q=p.copy();noise=gaussian_filter1d(rng.normal(size=q.shape),1.2,axis=0);q+=noise*(.012+layer*.009)
  depth=gaussian_filter1d(rng.normal(size=len(q)),3)*.13
  paths.append((q,t,layer,depth,int(rng.integers(0,13))))

# Long forks from the previously validated 3D point-charge growth solver.
# Each complete connected tree is transformed into a local sigil discharge.
forks=[]
anchors=np.flatnonzero(emit)[::max(1,int(emit.sum()/90))]
for j,i in enumerate(anchors):
 z=np.load(R/f'bending-rebuild-v5/laplacian-forked-3d-{j%10:02}.npz');p=z['points'].copy();parent=z['parent'];strength=z['strength'];trunk=z['trunk']
 p-=p[0];span=max(.1,np.linalg.norm(p[trunk],axis=1).max());p*=.24/span
 angle=rng.uniform(0,2*np.pi);c,s=np.cos(angle),np.sin(angle);x=p[:,0]*c-p[:,2]*s;zz=p[:,0]*s+p[:,2]*c
 p[:,0]=x+points[i,0];p[:,2]=zz+points[i,1]
 u=(p[:,0]/11.4+.5)*1023;v=((p[:,2]-2.95)/6.4125+.5)*575
 support=map_coordinates(sdf,[v,u],order=1,mode='constant',cval=-1)
 valid=(strength>.025)&(support>-.026)
 forks.append((p,parent,strength,valid,float(times[i]),j%13))

def project(p,depth=0):
 # Orthographic registration with a small depth-dependent optical parallax.
 return np.column_stack(((p[:,0]+np.asarray(depth)*.04)/11.4*W+W/2,H/2-(p[:,1]-2.95)/6.4125*H)).round().astype(np.int32)

def pulse(t,g):
 # Nonuniform stroke trains; three returns reuse each ionized channel.
 phase=(t-.017*g)%( .19+.007*g)
 return .06+1.9*np.exp(-(phase/.012)**2)+.65*np.exp(-((phase-.039)/.010)**2)+.22*np.exp(-((phase-.104)/.012)**2)

enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r','30','-i','-','-an','-c:v','libx264','-threads','2','-crf','16','-preset','fast','-pix_fmt','yuv420p','-movflags','+faststart',str(B/f'lightning-{variant}.mp4')],stdin=subprocess.PIPE)
start=time.time()
for f in range(300):
 t=f/30;active=np.clip((t-arrival)/.14,0,1);active*=active*(3-2*active)
 supply=mask*active*(t<6.2)*(.62+.2*np.sin(xx*.31+yy*.37-t*8)*np.sin(xx*.087-yy*.12+t*5))
 # Diffusion, attachment and quadratic recombination, integrated at 120 Hz.
 for _ in range(4):
  charge=gaussian_filter(charge,.19);charge+=supply*(1/120)*4.2;charge/=1+(1/120)*(3.8+charge*2.5)
 field=np.zeros((H,W),np.float32);alive=np.exp(-max(0,t-6.2)*12)
 for p,ts,layer,depth,g in paths:
  q=project(p,depth);ready=ts<=t;ids=np.flatnonzero(ready)
  if len(ids)<2:continue
  power=float(pulse(t,g)*alive*(1,.24,.10)[layer]);cv2.polylines(field,[q[:ids[-1]+1]],False,power,1,cv2.LINE_AA)
 for p,parent,strength,valid,born,g in forks:
  if t<born:continue
  q=project(p[:,[0,2]],p[:,1]);power=pulse(t,g)*alive*.27
  for j in np.flatnonzero(valid):
   if j and parent[j]>=0 and valid[parent[j]]:cv2.line(field,tuple(q[parent[j]]),tuple(q[j]),float(power*strength[j]),1,cv2.LINE_AA)
 core=gaussian_filter(field,.48);near=gaussian_filter(field,2.0);halo=gaussian_filter(field,9)
 c=cv2.resize(np.flipud(charge),(W,H),interpolation=cv2.INTER_CUBIC).clip(0)
 # Channel scattering only; distant background remains exactly black.
 linear=core[...,None]*np.array([3.8,5.8,9.5],np.float32)+near[...,None]*np.array([.4,1.2,4],np.float32)+halo[...,None]*np.array([.1,.24,.85],np.float32)
 linear+=c[...,None]*np.array([.018,.054,.16],np.float32)
 rgb=np.clip(linear*(2.51*linear+.03)/(linear*(2.43*linear+.59)+.14),0,1);rgb=np.where(rgb<=.0031308,12.92*rgb,1.055*rgb**(1/2.4)-.055);pixels=(rgb*255).astype('uint8');enc.stdin.write(pixels.tobytes())
 if f in [20,60,96,120,150,180,210,240,270,299]:Image.fromarray(pixels).resize((1440,810)).save(O/f'{f:04}.jpg',quality=94)
 if f%30==0:
  row=dict(frame=f,finite=bool(np.isfinite(charge).all()),charge=float(charge.sum()),seconds=round(time.time()-start,1));rows.append(row);print(json.dumps(row),flush=True)
 if f==120 and '--ungated' not in sys.argv:
  print('REVIEW GATE lightning '+variant,flush=True)
  while not (B/f'continue-lightning-{variant}').exists():time.sleep(.5)
enc.stdin.close();assert enc.wait()==0
(O/'report.json').write_text(json.dumps(dict(frames=300,fps=30,variant=variant,method=__doc__,channelPaths=len(paths),transformedLaplacianTrees=len(forks),rows=rows),indent=2),encoding='utf-8');print('COMPLETE',flush=True)
