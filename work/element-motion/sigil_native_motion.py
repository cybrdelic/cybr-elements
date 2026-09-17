from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter1d
with np.load(Path(__file__).resolve().parent/'sigil-native/c-stroke.npz') as d:P=d['points'];T=d['times']
MODE='arc';START=.15;WRITE=1.45
V=np.gradient(P,T,axis=0);V=gaussian_filter1d(V,2,axis=0);A=np.unwrap(np.arctan2(V[:,1],V[:,0]));OMEGA=gaussian_filter1d(np.gradient(A,T),4)
def pose(t):
 p=np.array([np.interp(t,T,P[:,i]) for i in range(2)]);v=np.array([np.interp(t,T,V[:,i]) for i in range(2)]);speed=np.linalg.norm(v);direction=v/max(speed,1e-8)
 return p,direction,float(START<=t<=START+WRITE),speed
def turn_rate(t):return float(np.clip(np.interp(t,T,OMEGA),-12,12)) if START<=t<=START+WRITE else 0.
