"""One moving nozzle. The path never touches emitted gas or its velocity."""
import os
import numpy as np
from scipy.interpolate import CubicSpline
from flow_paths import paths

MODE='word'
WRITE=3.1
START=.35
if MODE=='arc':
    p=np.array([[-3.5,1.2],[-2.4,1.6],[-1.2,2.65],[.05,2.7],[.75,2.0],[-.10,1.5],[-.7,2.1],[.75,2.85],[2.5,2.4]])
    t=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    p=CubicSpline(t,p,axis=0,bc_type='natural')(np.linspace(0,t[-1],2200))
    on=np.ones(len(p))
else:
    points=[];flags=[]
    for curve in paths():
        if points:
            bridge=np.linspace(points[-1][-1],curve['points'][0],24)[1:-1]
            points.append(bridge);flags.append(np.zeros(len(bridge)))
        points.append(curve['points']);flags.append(np.ones(len(curve['points'])))
    p=np.concatenate(points);on=np.concatenate(flags)
distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
keep=np.r_[True,np.diff(distance)>1e-8];p=p[keep];on=on[keep];distance=distance[keep]
length=distance[-1]

def pose(t):
    u=np.clip((t-START)/WRITE,0,1)
    q=u*length
    v=np.array([np.interp(q,distance,p[:,k]) for k in range(2)])
    a=np.array([np.interp(max(0,q-.005),distance,p[:,k]) for k in range(2)])
    b=np.array([np.interp(min(length,q+.005),distance,p[:,k]) for k in range(2)])
    direction=(b-a)/max(np.linalg.norm(b-a),1e-9)
    emission=np.interp(q,distance,on)*min(1,max(0,(t-START)/.035))*min(1,max(0,(START+WRITE-t)/.025))
    return v,direction,emission,length/WRITE

def turn_rate(t):
    da=pose(t-.004)[1];db=pose(t+.004)[1]
    return np.clip(np.arctan2(da[0]*db[1]-da[1]*db[0],np.dot(da,db))/.008,-3.,3.)
