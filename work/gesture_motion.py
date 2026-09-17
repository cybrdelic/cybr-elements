"""One uninterrupted calligraphic gesture. Only the moving nozzle follows it."""
import numpy as np
from scipy.interpolate import CubicSpline

MODE='gesture'
START=.08
# A single flowing cybrdelic gesture: no disconnected glyphs or pen lifts.
anchors=np.array([
 [-6.3,1.0],[-4.2,2.9],[-4.8,2.85],[-5.,2.2],[-4.6,1.4],[-3.9,1.65],
 [-3.7,2.9],[-3.3,1.5],[-2.8,2.85],[-3.25,.75],[-3.95,.35],[-3.7,1.3],
 [-2.6,2.2],[-2.45,3.2],[-2.8,3.5],[-2.95,2.1],[-2.55,1.25],
 [-1.9,1.7],[-2.,2.35],[-2.6,2.35],[-2.6,1.4],
 [-1.55,2.5],[-1.1,2.6],[-1.45,1.3],[-.65,1.7],
 [-.2,2.4],[-.7,2.7],[-1.,1.95],[-.5,1.3],[.1,2.0],
 [.25,3.4],[-.15,3.2],[0.,1.35],
 [.9,2.2],[1.5,2.3],[1.2,2.8],[.6,2.3],[1.,1.4],[1.8,1.5],
 [2.1,3.45],[1.7,3.2],[1.8,1.6],[2.5,1.25],
 [2.9,2.6],[2.75,1.7],[3.2,1.35],
 [4.05,2.75],[3.45,2.8],[3.3,2.0],[3.8,1.3],[4.5,1.7],[6.5,2.7]
],float)
anchors[:,0]*=.88
anchors[:,1]=anchors[:,1]*.8+.15
d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(anchors,axis=0),axis=1))]
curve=CubicSpline(d,anchors,axis=0,bc_type='natural')
q=np.linspace(0,d[-1],9000)
p=curve(q)
distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
v=curve(q,1);acc=curve(q,2)
curvature=np.abs(v[:,0]*acc[:,1]-v[:,1]*acc[:,0])/np.maximum(np.linalg.norm(v,axis=1)**3,1e-8)
# Accelerate through open reaches; settle through tighter turns.
speed=3.05+1.4/(1+(curvature/.9)**2)
times=np.r_[0,np.cumsum(np.diff(distance)/((speed[1:]+speed[:-1])*.5))]
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
