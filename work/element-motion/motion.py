import numpy as np
from scipy.interpolate import CubicSpline
MODE='arc';START=.08;WRITE=1.6
points=np.array([[-3.6,1.1],[-2.1,1.45],[-.8,2.5],[.35,2.6],[1.15,1.65],[.15,1.1],[-.5,1.8],[.7,2.5],[2.6,2.0]])
s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))];curve=CubicSpline(s,points,axis=0);length=s[-1]
def pose(t):
 u=np.clip((t-START)/WRITE,0,1);p=curve(u*length);d=curve(u*length,1);d/=np.linalg.norm(d)
 on=np.clip((t-START)/.05,0,1)*np.clip((START+WRITE-t)/.10,0,1)
 return p,d,on,length/WRITE
def turn_rate(t):
 a=pose(t-.008)[1];b=pose(t+.008)[1]
 return np.clip(np.arctan2(a[0]*b[1]-a[1]*b[0],np.dot(a,b))/.016,-2.8,2.8)*float(t<START+WRITE+.1)
