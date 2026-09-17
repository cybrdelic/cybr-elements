"""02 electrode geometry with native 3D point-charge discharge growth/optics."""
import os
os.environ['OPENBLAS_NUM_THREADS']='2';os.environ['OMP_NUM_THREADS']='2'
from pathlib import Path
import ast,sys,json,time,subprocess
import numpy as np,cv2
from PIL import Image
from scipy.ndimage import map_coordinates,distance_transform_edt
R=Path(__file__).resolve().parent;B=R/'sigil-02-elements/lightning';B.mkdir(exist_ok=True);OUT=B/'frames';OUT.mkdir(exist_ok=True)
source=np.load(R/'sigil-02-v2/source.npz');mask=(source['support']>.5).astype('uint8');Z,X=mask.shape
contours,_=cv2.findContours(mask,cv2.RETR_LIST,cv2.CHAIN_APPROX_NONE)
guides=[];starts=[]
for contour in sorted(contours,key=lambda x:cv2.arcLength(x,True),reverse=True):
 q=contour[:,0].astype(float)
 if len(q)<20:continue
 q=np.vstack((q,q[:1]));p=np.column_stack((q[:,0]/(X-1)*14-7,.08*np.sin(q[:,0]*.065)+.065*np.cos(q[:,1]*.08),q[:,1]/(Z-1)*7.875-1.05))
 d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
 samples=np.arange(0,d[-1],.022);p=np.column_stack([np.interp(samples,d,p[:,j]) for j in range(3)])
 for begin in range(0,len(p)-3,65):
  g=p[begin:min(begin+68,len(p))]
  if len(g)<5:continue
  guides.append(g)
  coord=[(g[:,2]+1.05)/7.875*(Z-1),(g[:,0]+7)/14*(X-1)]
  starts.append(float(np.min(map_coordinates(source['arrival'],coord,order=1)))+.10)
EVENTS=np.array(starts)
native=(R/'bending-lightning-v5.py').read_text();node=ast.parse(native)
def fn(name):return ast.get_source_segment(native,next(n for n in node.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name))
ns={'__file__':str(R/'bending-lightning-v5.py')};exec(native[:native.index('if __name__')],ns)
ns.update(B=B,OUT=OUT,EVENTS=EVENTS)
grow=fn('grow');a=grow.index('    rng=');b=grow.index('    h=.052',a)
grow=grow[:a]+'''    rng=np.random.default_rng(18301+event*379)
    guide=guides[event];gtree=cKDTree(guide)
    stops=guide[np.unique(np.r_[np.arange(0,len(guide),12),len(guide)-1])]
    if len(stops)<2:stops=guide[[0,-1]]
''' + grow[b:]
grow=grow.replace('h=.052','h=.035').replace('distance/.62','distance/.18').replace('range(4400)','range(6500)')
grow=grow.replace('(.80 if (stage+event)%2 else -1.0)','(.25 if (stage+event)%2 else -.30)').replace('np.array([0,.32,0])','np.array([0,.16,0])')
grow=grow.replace('[:12]','[:7]')
ns['guides']=guides;exec(grow,ns)
def project(p,w=1920,h=1080):
 # Orthographic frontal camera matches the approved full 02 geometry.
 return np.column_stack(((p[:,0]/14+.5)*w,(.5-(p[:,2]-2.8875)/7.875)*h))
def exposure(f,event):
 t=f/30;end=t+1/30;main=fork=0.
 schedule=[(EVENTS[event],1.,.012),(EVENTS[event]+.061,.45,.008),(EVENTS[event]+.172,.22,.006)]
 for at,power in [(4.20,.8),(4.73,.55),(5.34,1.),(5.92,.65),(6.48,1.),(6.82,.38)]:
  schedule.extend([(at+.002*(event%4),power,.016),(at+.060,power*.35,.009)])
 for at,power,duration in schedule:
  e=max(0,min(end,at+duration)-max(t,at))*30
  main+=e*power;fork+=e*power
  # A short excited-channel afterglow, not a persistent illuminated font.
  if 0<t-at<.10:main+=power*.004*np.exp(-(t-at)/.024)
 leader=max(0,min(end,EVENTS[event])-max(t,EVENTS[event]-.055))*30*.012
 return main+leader,fork+leader
ns['project']=project;ns['exposure']=exposure
# Expand the existing 3D aerosol solve to the shared camera frustum.
aero=fn('Aerosol').replace('10.5','14.0').replace('5.90625','7.875').replace('1.903125','2.8875')
a=aero.index('        on=pose(f/30)');b=aero.index('        light=',a)
aero=aero[:a]+'''        on=float(.3<f/30<7.0)
        nozzle=np.exp(-self.source_distance/.055)*self.noise
''' + aero[b:]
ns['CAM']=np.array([0.,-13.,2.8875]);ns['TARGET']=np.array([0.,0.,2.8875]);ns['FORWARD']=np.array([0.,1.,0.]);ns['RIGHT']=np.array([1.,0.,0.]);ns['UP']=np.array([0.,0.,1.])
exec(aero,ns)
started=time.time();nets=[]
for i in range(len(guides)):nets.append(ns['grow'](i))
(B/'networks.json').write_text(json.dumps({'count':len(nets),'nodes':sum(len(n['points']) for n in nets),'method':'Native 3D point-charge growth with authored full 02 contour electrodes; disconnected branches and native exposed channel optics','events':EVENTS.tolist()},indent=2))
aerosol=ns['Aerosol']();cloud=np.concatenate([n['points'][n['trunk']] for n in nets]);co=np.column_stack(((cloud[:,1]/4.4+.5)*47,(.5-(cloud[:,2]-2.8875)/7.875)*111,(cloud[:,0]/14+.5)*199)).round().astype(int);co=np.clip(co,0,np.array(aerosol.shape)-1);support=np.ones(aerosol.shape,bool);support[tuple(co.T)]=False;aerosol.source_distance=distance_transform_edt(support,sampling=aerosol.spacing)
# Ray samples use the orthographic camera, not the older oblique perspective.
grid=np.indices((112,200));aerosol.rays=[np.array([np.full((112,200),d),grid[0].astype(float),grid[1].astype(float)]) for d in np.linspace(0,47,48)]
video=B.parent/'lightning-02.mp4';enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','-','-c:v','libx264','-threads','2','-preset','fast','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],stdin=subprocess.PIPE)
for f in range(294):
 pixels=ns['render'](f,nets,aerosol);enc.stdin.write(pixels.tobytes())
 if f%5==0 or f in [126,142,160,178,195,205,293]:Image.fromarray(pixels).resize((1280,720)).save(OUT/f'{f:04}.jpg',quality=94)
 if f%30==0:print('FRAME',f,'seconds',round(time.time()-started,1),flush=True)
 if f==160:
  print('LIGHTNING REVIEW GATE',flush=True)
  while not (B.parent/'continue-lightning').exists():time.sleep(.5)
enc.stdin.close();assert enc.wait()==0
(B.parent/'lightning-report.json').write_text(json.dumps({'frames':294,'networks':len(nets),'elapsed':time.time()-started,'aerosol':aerosol.rows},indent=2));print('LIGHTNING COMPLETE',flush=True)
