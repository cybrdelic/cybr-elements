import numpy as np
from scipy.interpolate import CubicSpline
from flow_paths import paths

def smooth(points):
    p=np.asarray(points,float)
    d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    return CubicSpline(d,p,axis=0)(np.linspace(0,d[-1],1200))

def table(p):
    d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    keep=np.r_[True,np.diff(d)>1e-8]
    return p[keep],d[keep]

entrance=table(smooth([[-5.1,.65],[-3.4,.70],[-.8,1.25],[.4,2.6],[-.9,3.1],[-3.,2.95],[-3.67,2.25]]))
exit_path=table(smooth([[4.0,1.6],[4.5,1.05],[2.5,.75],[1.3,1.6],[2.4,2.9],[4.6,3.05],[5.8,2.6]]))
glyphs=[]
for i in range(9):
    pieces=[v['points'] for v in paths() if v['letter']==i]
    pts=[];flags=[]
    for p in pieces:
        if pts:
            bridge=np.linspace(pts[-1][-1],p[0],24)[1:-1]
            pts.append(bridge);flags.append(np.zeros(len(bridge)))
        pts.append(p);flags.append(np.ones(len(p)))
    p=np.concatenate(pts);f=np.concatenate(flags)
    d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    keep=np.r_[True,np.diff(d)>1e-8]
    glyphs.append((p[keep],d[keep],f[keep]))

def sample(curve,u):
    p,d=curve[:2];q=np.clip(u,0,1)*d[-1]
    v=np.array([np.interp(q,d,p[:,k]) for k in range(2)])
    pa=np.array([np.interp(max(0,q-.01),d,p[:,k]) for k in range(2)])
    pb=np.array([np.interp(min(d[-1],q+.01),d,p[:,k]) for k in range(2)])
    tangent=pb-pa;tangent/=max(1e-8,np.linalg.norm(tangent))
    power=np.interp(q,d,curve[2]) if len(curve)>2 else 1.
    return v,tangent,power

def emitters(t):
    out=[]
    if .1<t<1.8:
        u=(t-.1)/1.7
        pos,dr,power=sample(entrance,u)
        out.append((pos,dr,min(1,(t-.1)/.07,(1.8-t)/.1),entrance[1][-1]/1.7,.11,3.5))
    for i,curve in enumerate(glyphs):
        start=1.84+i*.022;duration=.52
        if start<t<start+duration:
            u=(t-start)/duration
            pos,dr,power=sample(curve,u)
            out.append((pos,dr,power*min(1,u/.035,(1-u)/.035),curve[1][-1]/duration,.055,1.0))
    if 2.93<t<4.2:
        pos,dr,power=sample(exit_path,(t-2.93)/1.27)
        out.append((pos,dr,min(1,(t-2.93)/.08,(4.2-t)/.12),exit_path[1][-1]/1.27,.11,3.5))
    return out

def physical_time(screen):
    # Give the short, freely advecting lettering event a legible slow-motion beat.
    return np.interp(screen,[0,1.8,3.3,4.45,6.2,7.0],[0,1.8,2.56,2.85,4.6,5.4])

def turning(t):
    curve=entrance if t<1.8 else exit_path
    start,duration=(.1,1.7) if t<1.8 else (2.93,1.27)
    if not(start<t<start+duration):return 0.
    a=sample(curve,(t-start-.005)/duration)[1]
    b=sample(curve,(t-start+.005)/duration)[1]
    return np.clip(np.arctan2(a[0]*b[1]-a[1]*b[0],np.dot(a,b))/.01,-3,3)
