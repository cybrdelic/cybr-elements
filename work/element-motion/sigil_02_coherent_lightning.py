"""Contained electrical filament study using the complete approved glyph domain.

This is an authored discharge visualization, not a calibrated plasma solver.
Channel streamlines follow the source field, with boundary repulsion and curl.
Persistent fine channel families preserve the silhouette during the hold.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='2'
from pathlib import Path
import json,sys,subprocess,time
import numpy as np,cv2
from scipy.ndimage import gaussian_filter,map_coordinates
from PIL import Image
R=Path(__file__).resolve().parent;O=R/'sigil-02-coherent';O.mkdir(exist_ok=True);W,H=1920,1080;cv2.setNumThreads(2)
s=np.load(R/'sigil-02-v2/source.npz');sdf=s['sdf'];mask=sdf>0;hh,ww=mask.shape;scale=W/ww
gz,gx=np.gradient(sdf);yx=np.column_stack(np.nonzero(mask));arrival=cv2.resize(np.flipud(s['arrival']), (W,H),interpolation=cv2.INTER_LINEAR)
birth=.25+(arrival-.30)/3.60*1.75
def sample(a,p):return map_coordinates(a,[p[:,1],p[:,0]],order=1,mode='nearest')
def build(family):
 rng=np.random.default_rng(71831+family*367);noise=gaussian_filter(rng.normal(size=mask.shape).astype(np.float32),2.5);az,ax=np.gradient(noise);norm=max(.001,float(np.std(ax)));ax/=norm;az/=norm
 seeds=yx[rng.choice(len(yx),1000,replace=False)][:,::-1].astype(float);p=seeds.copy();active=np.ones(len(p),bool);paths=[[q.copy()] for q in p]
 for step in range(105):
  dx=sample(s['dirx'],p);dz=sample(s['dirz'],p);n=np.maximum(.01,np.hypot(dx,dz));dx/=n;dz/=n
  # Curl perturbations create connected filament bends, while the glyph field
  # contains them. This is a bending control, not a global atmospheric bolt.
  direction=np.column_stack((dx+.32*sample(az,p),dz-.32*sample(ax,p)))
  d=sample(sdf,p);edge=np.column_stack((sample(gx,p),sample(gz,p)));en=np.maximum(1e-5,np.linalg.norm(edge,axis=1));edge/=en[:,None]
  direction+=edge*np.maximum(0,(.035-d)/.035)[:,None]*2.2
  direction/=np.maximum(.01,np.linalg.norm(direction,axis=1))[:,None];new=p+direction*.8
  valid=sample(sdf,new)>.001;active&=valid
  for k in np.flatnonzero(active):paths[k].append(new[k].copy())
  p=np.where(active[:,None],new,p)
 field=np.zeros((H,W),np.float32)
 for k,path in enumerate(paths):
  if len(path)<6:continue
  q=np.asarray(path);q[:,1]=hh-1-q[:,1];q*=scale
  # Subpixel channels rendered directly at final size, with hierarchical power.
  power=float(.30+.7*rng.random()**3);layer=np.zeros((H,W),np.uint8)
  cv2.polylines(layer,[np.rint(q*16).astype(np.int32)],False,255,1,cv2.LINE_AA,shift=4)
  field+=layer.astype(np.float32)*(power/255)
 print('CHANNEL FAMILY',family,flush=True);return field
field_cache=O/'lightning-fields.npz'
if field_cache.exists():fields=np.load(field_cache)['fields']
else:
 fields=np.stack([build(k) for k in range(6)]);np.savez_compressed(field_cache,fields=fields)
start=time.time();plasma=np.zeros((H,W),np.float32);haze=plasma.copy();previous=None
def frame(f):
 global plasma,haze
 t=f/30;phase=t*12;family=int(phase)%6;nextfamily=(family+1)%6;u=phase%1
 # A dense persistent discharge with fine local changes; the whole glyph no
 # longer disappears between sparse macroscopic return strokes.
 excitation=(fields[family]*(1-u)+fields[nextfamily]*u)*.72+fields[(family+3)%6]*.16
 active=np.clip((t-birth)/.12,0,1)
 current=max(0,min(1,(6.15-t)/.35));excitation*=active*current
 plasma=plasma*np.exp(-1/(30*.065))+excitation*(1-np.exp(-1/(30*.065)))
 core=plasma;near=cv2.GaussianBlur(core,(0,0),1.25);corona=cv2.GaussianBlur(core,(0,0),5.0);halo=cv2.GaussianBlur(core,(0,0),14)
 haze=cv2.warpAffine(haze,np.array([[1,0,.12],[0,1,-.20]],np.float32),(W,H),flags=cv2.INTER_LINEAR)*np.exp(-1/(30*.32))+corona*.018
 linear=core[:,:,None]*np.array([2.8,3.2,3.8])+near[:,:,None]*np.array([.14,.30,.78])+corona[:,:,None]*np.array([.012,.04,.15])+halo[:,:,None]*np.array([.002,.007,.025])+haze[:,:,None]*np.array([.015,.03,.10])
 rgb=1-np.exp(-np.maximum(linear,0));rgb=np.where(rgb<=.0031308,12.92*rgb,1.055*rgb**(1/2.4)-.055)
 return np.rint(np.clip(rgb,0,1)*255).astype(np.uint8)
full='--full' in sys.argv
if full:
 enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r','30','-i','-','-c:v','libx264','-threads','2','-preset','slow','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(O/'lightning-candidate.mp4')],stdin=subprocess.PIPE)
out=O/('lightning-review' if full else 'lightning-pilot');out.mkdir(exist_ok=True)
for f in range(300 if full else 166):
 im=frame(f)
 if full:enc.stdin.write(im.tobytes())
 if f in [45,75,120,165,183,210,240,299]:Image.fromarray(im).resize((1280,720)).save(out/f'{f:04}.jpg',quality=95)
 if f%30==0:print('LIGHTNING',f,round(time.time()-start,1),flush=True)
if full:enc.stdin.close();assert enc.wait()==0
(O/('lightning-report.json' if full else 'lightning-pilot-report.json')).write_text(json.dumps(dict(frames=300 if full else 166,channelFamilies=6,channelsPerFamily=1000,writingEnds=2.0,holdUntil=5.8,currentOff=6.15,method='Guided electrical filament streamlines constrained by the approved glyph signed distance, temporal discharge and approximate corona/aerosol',limitations='Authored graphics model; not a calibrated plasma or atmospheric lightning simulation.'),indent=2))
print('LIGHTNING COMPLETE',flush=True)
