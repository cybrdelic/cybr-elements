"""Isolate one approved stroke and change only the accepted fire's motion input."""
from pathlib import Path
import numpy as np,json,hashlib,heapq
from scipy.ndimage import gaussian_filter1d,label
from skimage.morphology import skeletonize
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;B=R/'sigil-native';B.mkdir(exist_ok=True)
D=np.load(R/'sigil-v1/mark-01.npz');mask=D['mask'];yy,xx=np.indices(mask.shape);wx=(xx/1023-.5)*11.4;wz=2.95+(yy/575-.5)*6.4125
selected=mask&(wx< -2.76)&(wz>2.10)
labels,n=label(selected,np.ones((3,3)));sizes=np.bincount(labels.ravel());sizes[0]=0;selected=labels==sizes.argmax()
sk=skeletonize(selected);labels,n=label(sk,np.ones((3,3)));sizes=np.bincount(labels.ravel());sizes[0]=0;sk=labels==sizes.argmax()
coords=np.argwhere(sk);ids={tuple(p):i for i,p in enumerate(coords)};adj=[[] for _ in coords]
for i,(y,x) in enumerate(coords):
 for dy in [-1,0,1]:
  for dx in [-1,0,1]:
   j=ids.get((y+dy,x+dx))
   if j is not None and j!=i:adj[i].append((j,float(np.hypot(dx,dy))))
def distances(start):
 d=np.full(len(coords),np.inf);d[start]=0;parent=np.full(len(coords),-1);q=[(0,start)]
 while q:
  cost,i=heapq.heappop(q)
  if cost!=d[i]:continue
  for j,w in adj[i]:
   if cost+w<d[j]:d[j]=cost+w;parent[j]=i;heapq.heappush(q,(d[j],j))
 return d,parent
d,_=distances(int(np.argmax(coords[:,1])));a=int(np.argmax(np.where(np.isfinite(d),d,-1)));d,parent=distances(a);b=int(np.argmax(np.where(np.isfinite(d),d,-1)));path=[];i=b
while i>=0:path.append(i);i=parent[i]
pix=coords[path];p=np.column_stack(((pix[:,1]/1023-.5)*11.4,2.95+(pix[:,0]/575-.5)*6.4125))
if p[0,1]<p[-1,1]:p=p[::-1];pix=pix[::-1]
p=gaussian_filter1d(p,2.2,axis=0);center=(p.min(0)+p.max(0))/2;p=(p-center)*1.85+np.array([0,2.15]);dist=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];times=.15+dist/dist[-1]*1.45
np.savez_compressed(B/'c-stroke.npz',points=p,times=times)
im=Image.fromarray(np.flipud(selected.astype('uint8')*45)).convert('RGB');draw=ImageDraw.Draw(im);draw.line([(int(x),575-int(y)) for y,x in pix],fill=(255,160,90),width=2);im.save(B/'stroke-validation.png')
src=(R/'bending-fire.py').read_text(encoding='utf-8');revised=src.replace('from shared_motion import pose as nozzle_pose, turn_rate as nozzle_turn, WRITE, START, MODE','from sigil_native_motion import pose as nozzle_pose, turn_rate as nozzle_turn, WRITE, START, MODE')
revised=revised.replace("out = ROOT/'bending-rebuild/fire-frames'","out = ROOT/'sigil-native/fire-c'")
revised=revised.replace('out.mkdir(exist_ok=True)','out.mkdir(parents=True,exist_ok=True)')
revised=revised.replace("TOTAL=46 if a.pilot else round(DURATION*FPS)","TOTAL=72 if a.pilot else round(DURATION*FPS)")
revised=revised.replace("video=ROOT.parent.parent/'outputs/cybrdelic-type/elements/motion/bending/fire.mp4'","video=ROOT/'sigil-native/fire-c.mp4'")
revised=revised.replace("(ROOT/'bending-rebuild/fire-report.json')","(ROOT/'sigil-native/fire-c-report.json')")
revised=revised.replace("'-preset','fast','-crf','17'","'-threads','2','-preset','fast','-crf','17'")
(R/'sigil_native_fire.py').write_text(revised,encoding='utf-8')
(B/'scope.json').write_text(json.dumps(dict(source='bending-fire.py',sourceSha256=hashlib.sha256(src.encode()).hexdigest(),changes=['trajectory import','isolated output paths','72-frame trial length','ffmpeg thread cap'],preserved=['gas solver','reaction','vorticity','nozzle geometry and momentum','buoyancy','radiance','exposure','black backdrop'],curveLength=float(dist[-1]),start=.15,end=1.6),indent=2),encoding='utf-8')
print(json.dumps(dict(points=len(p),length=float(dist[-1]),output=str(B),changes='Motion input only; original solver and appearance untouched')))
