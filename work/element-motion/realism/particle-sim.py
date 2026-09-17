import sys,math,json,time
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R.parent));from shared_motion import pose
for K in sys.argv[1:] or ['sand','snow','pressure','flight']:
 rng=np.random.default_rng(712);N={'sand':26000,'snow':2600,'pressure':8000,'flight':1400}[K];pos=np.zeros((N,3));vel=np.zeros_like(pos)
 r=np.minimum(.032 if K=='sand' else .055,.0075/np.maximum(.035,rng.random(N))**.48)
 if K=='snow':r*=1.9
 birth=.08+rng.random(N)*1.6
 for i,b in enumerate(birth):
  p,d,_,_=pose(float(b));a=rng.uniform(0,math.tau);rr=(.22 if K in ['pressure','flight'] else .12)*rng.random()**.5;pos[i]=[p[0]-d[1]*rr*math.cos(a),rr*math.sin(a),p[1]+d[0]*rr*math.cos(a)];vel[i]=[d[0]*(.25 if K in ['pressure','flight'] else .9),rng.normal(0,.12),d[1]*(.25 if K in ['pressure','flight'] else .9)]
 history=[];vels=[];dt=1/180;start=time.time()
 for f in range(120):
  for sub in range(6):
   t=(f+sub/6)/30;active=birth<=t;idx=np.flatnonzero(active)
   if K in ['sand','snow']:
    g=.6+9.21*np.clip((t-1.85)/.4,0,1);vel[active,2]-=g*dt;vel[active]*=np.exp(-dt*(.3 if K=='sand' else 2.2))
    if K=='snow':vel[active,0]+=np.sin(pos[active,2]*6+t*3)*dt*.25;vel[active,1]+=np.cos(pos[active,0]*4+t*2)*dt*.2
   else:
    vel[active]*=math.exp(-dt*(3.2 if K=='pressure' else .5));p,d,on,_=pose(t);delta=pos[active][:,[0,2]]-p;rr=np.sum(delta**2,axis=1)+.03
    if .08<t<1.75:
     if K=='pressure':
      force=-delta*np.exp(-rr/.27)[:,None]*42;vel[np.ix_(idx,[0,2])]+=force*dt;vel[:,1]=0
     else:
      no=np.array([-d[1],d[0]])
      for sign in [-1,1]:
       dd=delta-sign*no*.18;rr2=np.sum(dd**2,axis=1)+.018;vortex=np.column_stack([-dd[:,1],dd[:,0]])*sign*(2.5*np.exp(-rr2/1.2)/rr2)[:,None];vel[np.ix_(idx,[0,2])]+=vortex*dt
      vel[:,1]+=np.sin(pos[:,0]*3+t*4)*np.exp(-rr/.4)*dt*.06
    if K=='pressure' and t>1.75:
     # Residual compression rebounds after the attracting source releases.
     vel[np.ix_(idx,[0,2])]+=delta*(np.exp(-rr/.8)*9*math.exp(-(t-1.75)*5))[:,None]*dt
   old=pos.copy();pos[active]+=vel[active]*dt
   if K!='flight' and len(idx)>2:
    # Position-based contact projection, then a Coulomb-like tangential loss.
    for it in range(2 if K=='sand' else 1):
     tree=cKDTree(pos[active]);pairs=tree.query_pairs(float(r.max()*2.0),output_type='ndarray')
     if not len(pairs):break
     a,b=idx[pairs[:,0]],idx[pairs[:,1]];delta=pos[b]-pos[a];dist=np.linalg.norm(delta,axis=1);over=r[a]+r[b]-dist;ok=over>0;a,b,delta,dist,over=a[ok],b[ok],delta[ok],dist[ok],over[ok]
     if not len(a):break
     normal=delta/np.maximum(1e-7,dist[:,None]);correction=normal*np.minimum(over,.015)[:,None]*.38;move=np.zeros_like(pos);np.add.at(move,a,-correction);np.add.at(move,b,correction);pos+=move
     rel=vel[b]-vel[a];tangent=rel-normal*np.sum(rel*normal,axis=1)[:,None];loss=tangent*(.07 if K=='sand' else .025);np.add.at(vel,a,loss);np.add.at(vel,b,-loss)
    # Contact projection does not inject separation velocity into overlapping births.
    vel[active]*=math.exp(-dt*.18)
   if K in ['sand','snow']:
    hit=active&(pos[:,2]<r);pos[hit,2]=r[hit];vel[hit,2]=np.abs(vel[hit,2])*.06;vel[hit,:2]*=.70
   if K=='pressure':pos[:,1]=.4
  framepos=pos.copy();framepos[~active,2]=-20;history.append(framepos.astype('f4'));vels.append(vel.astype('f4'))
 np.savez_compressed(R/f'{K}-sim.npz',positions=history,velocities=vels,radii=r.astype('f4'),birth=birth.astype('f4'))
 print(K,N,'contact-integrated frames',len(history),'seconds',round(time.time()-start,1),flush=True)
