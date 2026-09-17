"""Connected italic copperplate centerline; one continuous emitting nozzle."""
import numpy as np
MODE='script'
START=.08
points=[np.array([-1.5,.15])]
segments=[]
def B(a,b,c):
    start=points[-1];a=np.array(a);b=np.array(b);c=np.array(c)
    u=np.linspace(0,1,180)[1:,None]
    v=(1-u)**3*start+3*(1-u)**2*u*a+3*(1-u)*u*u*b+u**3*c
    segments.append(v);points.append(c)
def G(offset, curves):
    for a,b,c in curves:
        B((a[0]+offset,a[1]),(b[0]+offset,b[1]),(c[0]+offset,c[1]))
# c: open oval, generous counter and lifted exit.
G(0,[((-1,.15),(.0,1.1),(.76,1.04)),((.45,1.36),(-.05,.83),(.05,.35)),((.10,-.12),(.65,-.02),(1.02,.38))])
# y: a rounded bowl feeding a looped descender.
G(1.04,[((.05,.65),(.16,.91),(.23,1.06)),((-.04,.25),(.01,-.02),(.34,.05)),((.66,.15),(.79,.73),(.87,1.08)),((.64,.13),(.60,-.69),(.12,-.83)),((-.43,-1.03),(-.10,-.27),(1.03,.40))])
# b: ascender loop and round lower bowl.
G(2.09,[((.35,.85),(.87,1.9),(.48,1.88)),((.13,1.84),(-.12,.16),(.12,.05)),((.58,-.20),(1.03,.80),(.57,1.01)),((.40,1.12),(.22,.78),(.36,.63)),((.53,.41),(.86,.40),(1.06,.52))])
# r: restrained shoulder and a smooth baseline return.
G(3.12,[((.14,.84),(.24,1.1),(.27,1.10)),((.25,.72),(.62,.78),(.73,1.03)),((.63,.64),(.34,.14),(.57,.04)),((.72,-.02),(.90,.21),(1.06,.38))])
# d: oval then a slender looped ascender, returning into the connector.
G(4.02,[((.90,1.37),(.06,1.22),(.03,.39)),((.01,-.21),(.69,-.06),(.85,.85)),((1.02,1.45),(1.38,2.03),(1.06,1.91)),((.82,1.77),(.49,.12),(.79,.03)),((.98,-.02),(1.11,.24),(1.25,.40))])
# e: open loop, low rounded bowl.
G(5.18,[((.65,.93),(.90,1.17),(.54,1.10)),((.05,1.01),(-.10,.22),(.24,.05)),((.56,-.13),(.87,.19),(1.05,.40))])
# l: tall oval loop, not a vertical stick.
G(6.18,[((.54,1.07),(.95,2.04),(.58,1.93)),((.23,1.84),(-.09,.14),(.27,.03)),((.45,-.04),(.70,.22),(.89,.40))])
# i: short italic stem; continuous path deliberately omits detached dot.
G(7.00,[((.23,.67),(.30,.92),(.34,1.07)),((.23,.65),(.05,.14),(.27,.05)),((.45,-.06),(.64,.21),(.80,.42))])
# c and flowing terminal.
G(7.77,[((.59,1.16),(.78,1.15),(.83,.98)),((.48,1.38),(-.02,.88),(.04,.36)),((.07,-.12),(.63,-.06),(1.00,.31)),((1.63,.93),(2.03,.85),(2.63,1.30))])
p=np.vstack([[-1.5,.15],*segments])
# Common baseline, x-height and consistent 12 degree slant.
p[:,0]+=.16*p[:,1]
p[:,0]=(p[:,0]-4.43)*.92
p[:,1]=p[:,1]*.89+1.18
# Arc-length timing keeps the approved fast writing duration.
distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
v=np.gradient(p,axis=0);acc=np.gradient(v,axis=0)
curvature=np.abs(v[:,0]*acc[:,1]-v[:,1]*acc[:,0])/np.maximum(np.linalg.norm(v,axis=1)**3,1e-10)
speed=3.05+1.4/(1+(curvature/.9)**2)
times=np.r_[0,np.cumsum(np.diff(distance)/((speed[1:]+speed[:-1])*.5))]
scale=times[-1]/12.93
times/=scale;speed*=scale
WRITE=float(times[-1])
def pose(t):
    elapsed=np.clip(t-START,0,WRITE)
    q=np.interp(elapsed,times,distance)
    point=np.array([np.interp(q,distance,p[:,k]) for k in range(2)])
    before=np.array([np.interp(max(0,q-.008),distance,p[:,k]) for k in range(2)])
    after=np.array([np.interp(min(distance[-1],q+.008),distance,p[:,k]) for k in range(2)])
    direction=after-before;direction/=max(1e-8,np.linalg.norm(direction))
    on=min(1,max(0,(t-START)/.035))*min(1,max(0,(START+WRITE-t)/.05))
    return point,direction,on,float(np.interp(elapsed,times,speed))
def turn_rate(t):
    a=pose(t-.004)[1];b=pose(t+.004)[1]
    return np.clip(np.arctan2(a[0]*b[1]-a[1]*b[0],np.dot(a,b))/.008,-3.,3.)
