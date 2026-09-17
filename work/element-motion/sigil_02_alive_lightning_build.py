from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'sigil_02_coherent_lightning.py').read_text();s=s[:s.index('field_cache=')]
s=s.replace("O=R/'sigil-02-coherent'","O=R/'sigil-02-alive'").replace('71831+family*367','98217+family*367').replace('1000,replace=False','300,replace=False').replace('range(105)','range(115)')
s=s.replace("print('CHANNEL FAMILY'", "print('LIVE CHANNEL FAMILY'")
s+='''field_cache=O/'lightning-live-fields.npz'
if field_cache.exists():fields=np.load(field_cache)['fields']
else:
 fields=np.stack([build(k) for k in range(12)]);np.savez_compressed(field_cache,fields=fields)
base=np.load(R/'sigil-02-coherent/lightning-fields.npz')['fields'].mean(0)
birth=np.clip(birth,.25,2.15)
rng=np.random.default_rng(68122);events=[]
for k,start in enumerate(np.arange(.25,6.12,.115)):
 events.append((float(start+rng.uniform(-.045,.045)),int(rng.integers(0,12)),float(rng.uniform(.8,1.5))))
edge_yx=np.column_stack(np.nonzero((sdf>0)&(sdf<.019)));streamers=[]
for k in range(240):
 gy,gxx=edge_yx[rng.integers(len(edge_yx))];anchor=np.array([gxx,hh-1-gy],float)*scale
 direction=np.array([-gx[gy,gxx],gz[gy,gxx]],float);direction/=max(.0001,np.linalg.norm(direction))
 length=min(55,9/(1-rng.random()*.95)**.55);side=np.array([-direction[1],direction[0]]);nodes=[anchor]
 for j in range(1,7):nodes.append(anchor+direction*(length*j/6)+side*rng.normal(0,length*.11))
 branches=[np.asarray(nodes)]
 fork=nodes[3];branches.append(np.array([fork,fork+direction*length*.16+side*length*.23,fork+direction*length*.30+side*length*.37]))
 start=float(rng.uniform(.5,5.95));start=max(start,float(birth[int(anchor[1]),int(anchor[0])])+.07)
 streamers.append((start,branches,float(rng.uniform(.7,1.4))))
yy,xx=np.indices((H,W),dtype=np.float32);delay=.055*(xx/W)+.020*np.sin(xx*.015+yy*.009)+.012*np.cos(yy*.026-xx*.011)
start=time.time();plasma=np.zeros((H,W),np.float32);haze=plasma.copy()
def frame(f):
 global plasma,haze
 t=f/30;active=np.clip((t-birth)/.12,0,1);current=max(0,min(1,(6.15-t)/.35))
 # A faint conducting network retains the mark between local discharges.
 # The bright channels grow, return, and extinguish; the six-frame family
 # cycle from r3 is gone. No whole-frame flash is added.
 excitation=base*.24
 for begin,family,power in events:
  age=t-begin
  if age<-.05 or age>.42:continue
  local=age-delay*(.7+.08*family)
  leader=np.clip(local/.018,0,1)*np.exp(-np.maximum(0,local-.025)/.075)
  returned=.65*np.exp(-((local-.115)/.021)**2)
  excitation=excitation+fields[family]*(leader+returned)*power*2.1
 excitation*=active*current
 # Short, rooted corona leaders briefly leave the mark. Their branching
 # contour changes distinguish a discharge from a permanently lit engraving.
 arcs=np.zeros((H,W),np.float32)
 for begin,paths,power in streamers:
  age=t-begin
  if age<0 or age>.18:continue
  strength=power*np.exp(-age/.055);growth=min(1,age/.025+.3)
  for path in paths:
   q=path[:max(2,int(len(path)*growth))];cv2.polylines(arcs,[np.rint(q*16).astype(np.int32)],False,float(strength),1,cv2.LINE_AA,shift=4)
 excitation+=arcs*current
 plasma=plasma*np.exp(-1/(30*.038))+excitation*(1-np.exp(-1/(30*.038)))
 core=plasma;near=cv2.GaussianBlur(core,(0,0),1.25);corona=cv2.GaussianBlur(core,(0,0),5.0);halo=cv2.GaussianBlur(core,(0,0),14)
 haze=cv2.warpAffine(haze,np.array([[1,0,.15],[0,1,-.24]],np.float32),(W,H),flags=cv2.INTER_LINEAR)*np.exp(-1/(30*.36))+corona*.018
 linear=core[:,:,None]*np.array([2.8,3.2,3.8],np.float32)+near[:,:,None]*np.array([.14,.30,.78],np.float32)+corona[:,:,None]*np.array([.012,.04,.15],np.float32)+halo[:,:,None]*np.array([.002,.007,.025],np.float32)+haze[:,:,None]*np.array([.015,.03,.10],np.float32)
 rgb=1-np.exp(-np.maximum(linear,0));rgb=np.where(rgb<=.0031308,12.92*rgb,1.055*rgb**(1/2.4)-.055)
 return np.rint(np.clip(rgb,0,1)*255).astype(np.uint8)
full='--full' in sys.argv
if full:enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r','30','-i','-','-c:v','libx264','-threads','2','-preset','slow','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(O/'lightning-candidate.mp4')],stdin=subprocess.PIPE)
out=O/('lightning-review' if full else 'lightning-quick' if '--quick' in sys.argv else 'lightning-pilot');out.mkdir(exist_ok=True)
for f in (range(80,132) if '--quick' in sys.argv else range(300 if full else 166)):
 im=frame(f)
 if full:enc.stdin.write(im.tobytes())
 if f in [30,45,75,78,81,84,90,120,123,126,129,165,183,210,240,299]:Image.fromarray(im).resize((1280,720)).save(out/f'{f:04}.jpg',quality=95)
 if f%30==0:print('LIGHTNING',f,round(time.time()-start,1),flush=True)
if full:enc.stdin.close();assert enc.wait()==0
(O/('lightning-report.json' if full else 'lightning-pilot-report.json')).write_text(json.dumps(dict(frames=300 if full else 166,channelFamilies=12,channelsPerFamily=300,events=len(events),seed=68122,holdUntil=5.8,currentOff=6.15,method='Stochastic local leader propagation, short return pulses and afterglow over a persistent low-current glyph network',limitations='Authored visual discharge model, not calibrated plasma physics.'),indent=2))
print('LIGHTNING COMPLETE',flush=True)
'''
(R/'sigil_02_alive_lightning.py').write_text(s)
print('Built non-looping discharge pilot.')
