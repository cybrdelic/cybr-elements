import sys,math,random,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from helpers import *
K=sys.argv[sys.argv.index('--kind')+1];s,cam=setup(64);bloom(s,1.7,-.70);core,e=emission('Return stroke plasma',(.54,.68,1),160);branch,eb=emission('Stepped leaders',(.18,.35,1),30)
bpy.ops.mesh.primitive_plane_add(size=100);floor=bpy.context.object;floor.visible_camera=False;floor.data.materials.append(material('Low key contact floor',(.004,.005,.008),.32))
objects=[];events=[.14,.37,.66,.93,1.18,1.48,1.75,2.15,2.58,3.02,3.52];mainpath=[]
for u in np.linspace(0,1,220):p0,d,_,_=pose(.08+u*1.6);mainpath.append(Vector((p0[0],0,p0[1])))
if K=='lightning-redirection':
 copper=material('Copper receiving conductor',(.12,.045,.018),.22,metal=1);conductor=curve('Conducting path',mainpath,.025,copper)
 for point in [mainpath[0],mainpath[-1]]:
  bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=.10,location=point);bpy.context.object.data.materials.append(copper)
def jag(a,b,depth,rng):
 if depth==0:return [a,b]
 v=b-a;mid=(a+b)*.5+Vector((rng.gauss(0,1),rng.gauss(0,.4),rng.gauss(0,1)))*v.length*.18
 return jag(a,mid,depth-1,rng)[:-1]+jag(mid,b,depth-1,rng)
def channel(pts,r,mat):
 if len(pts)>1:objects.append(curve('Ionized discharge',pts,r,mat))
take=selected((20,37,53,78,106))
for f in sorted(take):
 for o in objects:
  cu=o.data;bpy.data.objects.remove(o,do_unlink=True);bpy.data.curves.remove(cu)
 objects=[];t=f/30;event=max([i for i,b in enumerate(events) if b<=t],default=-1);age=t-events[event] if event>=0 else 10;rng=random.Random(173+event*991)
 if K=='lightning':
  active=age<.10;front=np.clip((min(t,1.68)-.08)/1.6,0,1)
  if active and front>.01:
   # Each flash keeps its tree during leader growth and return strokes.
   start=max(0,front-.65);anchors=[]
   for u in np.linspace(start,front,12):p0,d,_,_=pose(.08+u*1.6);anchors.append(Vector((p0[0],0,p0[1])))
   pts=[]
   for a,b in zip(anchors[:-1],anchors[1:]):pts.extend(jag(a,b,3,rng)[:-1])
   pts.append(anchors[-1]);reveal=1 if age>.018 else .65;pts=pts[:max(2,int(len(pts)*reveal))];channel(pts,.0032,core)
   for j in range(4,len(pts)-1,9):
    a=pts[j];direction=(pts[j]-pts[max(0,j-3)]).normalized();normal=Vector((-direction.z,rng.uniform(-.5,.5),direction.x))*rng.choice([-1,1]);tip=a+direction*rng.uniform(.08,.45)+normal*rng.uniform(.25,.9);bp=jag(a,tip,4,rng);channel(bp,.0011,branch)
    for k in [5,10]:channel(jag(bp[k],bp[k]+normal*rng.uniform(.12,.35)+Vector((0,.05,-.1)),3,rng),.00045,branch)
   e.inputs[1].default_value=(220 if .018<age<.052 else 18);eb.inputs[1].default_value=(35 if age<.055 else 5)
 else:
  # Receive, conduct, then release: three spatially distinct discharge phases.
  if .10<t<.35:
   pts=jag(Vector((-5.1,-.05,3.7)),mainpath[0],7,rng);channel(pts,.004,core)
  if .25<t<1.70:
   front=np.clip((t-.08)/1.6,0,1);j=int(front*(len(mainpath)-1));lo=max(0,j-24);pts=[p+Vector((0,-.035,0)) for p in mainpath[lo:j+1]];channel(pts,.007,core)
   if len(pts)>2:
    for k in [0,len(pts)//2,-1]:channel(jag(pts[k],pts[k]+Vector((rng.uniform(-.2,.2),-.1,rng.uniform(-.25,.25))),4,rng),.001,branch)
  if 1.72<t<2.12 or (event>=0 and age<.07 and t>2.1):
   pts=jag(mainpath[-1],Vector((5.1,-.2,3.7)),7,rng);channel(pts,.004,core)
   for j in range(10,len(pts)-5,23):channel(jag(pts[j],pts[j]+Vector((rng.uniform(-.25,.5),-.15,rng.uniform(-.6,.6))),4,rng),.001,branch)
 finish(s,K,f)
(R/f'{K}-mechanism.json').write_text(json.dumps({'frames':120,'emitter':'shared-trail.json','mechanism':'leader/return-stroke event tree' if K=='lightning' else 'receive-conduct-release sequence','pulseTimes':events}),encoding='utf-8')
