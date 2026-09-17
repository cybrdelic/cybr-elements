import numpy as np
MODE='sans'
START=.08
curves=[]
def poly(points):
    out=[]
    for a,b in zip(points[:-1],points[1:]):
        out.extend(np.linspace(a,b,max(2,int(np.linalg.norm(np.array(b)-a)*180)),endpoint=False))
    return np.vstack([out,points[-1]])
def arc(cx,cy,rx,ry,a,b):
    t=np.linspace(a,b,300);return np.c_[cx+rx*np.cos(t),cy+ry*np.sin(t)]
def add(i,p):
    p=np.array(p);p[:,0]+=(i*1.02-4.47);p[:,1]+=1.05;curves.append(p)
c=arc(.40,.65,.38,.65,.23*np.pi,1.77*np.pi)
add(0,c)
add(1,poly([[0,1.3],[.38,.69],[.76,1.3]]));add(1,poly([[.38,.69],[.38,0]]))
add(2,poly([[0,0],[0,1.3]]));add(2,np.vstack([poly([[0,1.3],[.34,1.3]]),arc(.34,.975,.40,.325,np.pi/2,-np.pi/2),poly([[.34,.65],[0,.65],[.34,.65]]),arc(.34,.325,.43,.325,np.pi/2,-np.pi/2),poly([[.34,0],[0,0]])]))
add(3,poly([[0,0],[0,1.3]]));add(3,np.vstack([poly([[0,1.3],[.34,1.3]]),arc(.34,.975,.40,.325,np.pi/2,-np.pi/2),poly([[.34,.65],[0,.65]])]));add(3,poly([[.30,.65],[.78,0]]))
add(4,np.vstack([poly([[0,0],[0,1.3],[.20,1.3]]),arc(.20,.65,.56,.65,np.pi/2,-np.pi/2),poly([[.20,0],[0,0]])]))
add(5,poly([[.75,1.3],[0,1.3],[0,0],[.75,0]]));add(5,poly([[0,.65],[.64,.65]]))
add(6,poly([[0,1.3],[0,0],[.73,0]]))
add(7,poly([[.10,1.3],[.66,1.3]]));add(7,poly([[.38,1.3],[.38,0]]));add(7,poly([[.1,0],[.66,0]]))
add(8,c)
# Keep a single moving source. Shut emission during the short inter-stroke moves.
lengths=[np.linalg.norm(np.diff(p,axis=0),axis=1).sum() for p in curves]
travel=.10; drawtotal=12.93-travel*(len(curves)-1)
times=[];paths=[];emit=[];now=0
for i,(p,l) in enumerate(zip(curves,lengths)):
    if i:
        bridge=np.linspace(curves[i-1][-1],p[0],30)
        times.extend(now+np.linspace(0,travel,30,endpoint=False));paths.extend(bridge);emit.extend([0]*30);now+=travel
    d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];duration=drawtotal*l/sum(lengths)
    times.extend(now+d/d[-1]*duration);paths.extend(p);emit.extend([1]*len(p));now+=duration
p=np.array(paths);times=np.array(times);emit=np.array(emit);WRITE=now
# Duplicate boundary samples are harmless for interpolation.
def pose(t):
    elapsed=np.clip(t-START,0,WRITE)
    point=np.array([np.interp(elapsed,times,p[:,k]) for k in range(2)])
    before=np.array([np.interp(max(0,elapsed-.003),times,p[:,k]) for k in range(2)])
    after=np.array([np.interp(min(WRITE,elapsed+.003),times,p[:,k]) for k in range(2)])
    v=(after-before)/.006;speed=np.linalg.norm(v);direction=v/max(speed,1e-8)
    on=float(np.interp(elapsed,times,emit)) if START<t<START+WRITE else 0.
    return point,direction,on,min(5.,speed)
def turn_rate(t):
    a=pose(t-.004)[1];b=pose(t+.004)[1]
    return np.clip(np.arctan2(a[0]*b[1]-a[1]*b[0],np.dot(a,b))/.008,-3.,3.)
