import sys,math,json,subprocess,time
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFilter,ImageChops
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from shared_motion import pose,DATA
O=R.parent.parent/'outputs/cybrdelic-type/elements/motion/subelements';O.mkdir(exist_ok=True)
W,H=1920,1080
KINDS=['lightning','lightning-redirection','combustion','energy','seismic','sound','flight','spirit-projection']
if len(sys.argv)>1:KINDS=sys.argv[1:]
def pixel(p):return np.array([(p[0]+5.25)*W/10.5,120+(4.2-p[1])*768/4.2])
times=np.linspace(.08,1.68,350);path=np.array([pixel(pose(float(t))[0]) for t in times]);tangent=np.gradient(path,axis=0);tangent/=np.linalg.norm(tangent,axis=1)[:,None];normal=np.column_stack([-tangent[:,1],tangent[:,0]])
def color(rgb,a):return tuple(int(min(255,max(0,v*a))) for v in rgb)
def line(draw,pts,col,width=1):
 if len(pts)>1:draw.line([tuple(p) for p in pts],fill=col,width=max(1,int(width)),joint='curve')
def render(kind,f):
 t=f/30;im=Image.new('RGB',(W,H));d=ImageDraw.Draw(im);head=int(np.clip((t-.08)/1.6,0,1)*349);rng=np.random.default_rng(1203+f//2)
 if kind in ['lightning','lightning-redirection']:
  if .08<t<2.6:
   returning=kind=='lightning-redirection' and t>1.7;h=349-int(np.clip((t-1.7)/.75,0,1)*349) if returning else head
   begin=max(0,h-180) if not returning else h;end=h if not returning else min(349,h+180)
   pulse=(.14+.86*(math.sin(t*45)>.15))*math.exp(-max(0,t-1.7)*2);pts=path[begin:end+1].copy();n=normal[begin:end+1];jitter=rng.normal(0,5,len(pts));jitter[::8]*=2.4;pts+=n*jitter[:,None]
   col=(255,165,55) if returning else (65,140,255);line(d,pts,color(col,pulse),5);line(d,pts,color((210,239,255),pulse),2)
   for j in range(8,len(pts)-4,13):
    if rng.random()>.63:continue
    length=rng.uniform(15,100);q=pts[j].copy();branch=[q.copy()];direction=n[j]*rng.choice([-1,1])+.45*tangent[begin+j]
    for k in range(10):q=q+direction*length/10+rng.normal(0,3,2);branch.append(q.copy())
    line(d,branch,color(col,pulse*.55),1)
 elif kind=='combustion':
  if .08<t<1.68:
   begin=max(0,head-60);pts=path[begin:head+1];line(d,pts,(155,72,22),5);line(d,pts,(235,223,203),2)
   for born in np.arange(.12,1.6,.14):
    age=t-born
    if 0<age<.5:
     q=pixel(pose(float(born))[0]);rad=8+age*75;alpha=math.exp(-age*5);d.ellipse((q[0]-rad*.38,q[1]-rad,q[0]+rad*.38,q[1]+rad),outline=color((170,159,135),alpha),width=2)
  age=t-1.68
  if age>0:
   cx,cy=path[-1];radius=20+210*(1-math.exp(-age*2.0));cy-=age*28;box=int(radius*1.8);x=np.arange(-box,box+1);xx,yy=np.meshgrid(x,x);r=np.sqrt(xx*xx+yy*yy);ang=np.arctan2(yy,xx)
   curl=(np.sin(xx*.038+age*4)*np.sin(yy*.043-age*2)+.45*np.sin(xx*.09+yy*.077+age*6)+.2*np.cos(xx*.19-yy*.15))/1.65
   edge=radius*(.9+.11*np.sin(ang*7+age)+.08*np.cos(ang*13-age*2));density=np.clip((edge-r)/(radius*.22)+curl*.9,0,1);heat=np.clip((1-r/(radius*1.1))*.8+curl*.35,0,1)*math.exp(-age*1.4)
   rgb=np.stack([density*(heat*2.8+.11),density*(heat**2*3.2+.10),density*(heat**4*3+.085)],axis=-1);rgb=rgb/(1+rgb);rgb=np.clip(rgb*255,0,255).astype(np.uint8);plume=Image.fromarray(rgb);im.paste(plume,(int(cx)-box,int(cy)-box));d=ImageDraw.Draw(im)
   for i in range(120):
    rr=np.random.default_rng(701+i);v=rr.normal(0,1,2);v/=max(1e-8,np.linalg.norm(v));speed=rr.uniform(90,360);q=np.array([cx,cy])+v*speed*(1-math.exp(-age*1.7))/1.7+np.array([0,60*age*age]);a=math.exp(-age*(1.8+rr.random()*2));line(d,[q-v*5,q],color((255,110,20),a),1)
   if age<.55:
    rad=age*1000;d.ellipse((cx-rad,cy-rad*.65,cx+rad,cy+rad*.65),outline=color((230,215,188),math.exp(-age*8)),width=2)
 elif kind in ['energy','spirit-projection','flight','heat']:
  if .08<t<3.8:
   copies=4 if kind=='spirit-projection' else 1
   for copy in range(copies):
    age=max(0,t-1.65);offset=np.array([copy*age*18,-copy*age*40]);end=head if t<1.68 else 349;begin=max(0,end-(100 if kind=='flight' else 300));decay=math.exp(-age*(1.6 if kind=='flight' else .8))
    for strand in range(26 if kind!='flight' else 15):
     u=np.arange(begin,end+1);phase=u*.06-t*5+strand*.41;amplitude=(6+strand*.7)*np.sin(np.linspace(0,math.pi,len(u)))**.5;pts=path[begin:end+1]+normal[begin:end+1]*(amplitude*np.sin(phase))[:,None]+offset
     if kind=='energy':
      col=(35,125,255) if strand%2 else (255,115,20);pts+=normal[begin:end+1]*((14*np.sin(u*.045-t*2)+10)*(1 if strand%2 else -1))[:,None]
     elif kind=='flight':col=(130,185,210)
     elif kind=='heat':col=(175,95,50)
     else:col=(130,220,190)
     line(d,pts,color(col,decay*(.22 if copy else .5)),1 if strand%5 else 2)
 elif kind in ['seismic','sound','pressure']:
  if kind=='seismic':
   # Dim ground reference; rings are a visualization of sensing, not emitted light in canon.
   for y in range(500,940,55):line(d,[(280,y),(1640,y)],(9,10,9),1)
   for x in range(350,1650,100):line(d,[(960+(x-960)*.55,490),(x,940)],(9,10,9),1)
  for born in np.arange(.08,1.7,.12 if kind=='sound' else .22):
   age=t-born
   if age<=0 or age>1.5:continue
   q=pixel(pose(float(born))[0]);radius=12+(1.5-age)*220 if kind=='pressure' else 12+age*(210 if kind=='sound' else 260);alpha=math.exp(-age*1.4);yscale=.78 if kind=='sound' else .28;col=(140,194,215) if kind in ['sound','pressure'] else (197,137,62)
   pts=np.array([[q[0]+radius*math.cos(a),q[1]+radius*yscale*math.sin(a)] for a in np.linspace(0,math.tau,180)]);line(d,pts,color(col,alpha),4)
   if kind=='sound':
    pts2=(pts-q)*.94+q;line(d,pts2,color(col,alpha*.25),4)
 if kind not in ['seismic','sound','pressure']:
  bloom=im.filter(ImageFilter.GaussianBlur(7));wide=im.filter(ImageFilter.GaussianBlur(23));im=ImageChops.add(im,ImageChops.add(bloom,wide,scale=2),scale=1)
 if kind!='combustion':im=im.point([min(255,int(i*2.4)) for i in range(256)]*3)
 return im
for kind in KINDS:
 start=time.time();folder=R/'subelements'/f'{kind}-frames';folder.mkdir(exist_ok=True)
 enc=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r','30','-i','-','-c:v','libx264','-threads','2','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(O/f'{kind}.mp4')],stdin=subprocess.PIPE)
 for f in range(120):
  im=render(kind,f);enc.stdin.write(im.tobytes())
  if f%10==0:im.resize((1280,720)).save(folder/f'{f:04}.jpg',quality=90)
 enc.stdin.close();assert enc.wait()==0
 render(kind,43 if kind.startswith('lightning') else 40 if kind!='combustion' else 58).save(O/f'{kind}.jpg',quality=94);print('ENERGY',kind,round(time.time()-start,1),flush=True)
