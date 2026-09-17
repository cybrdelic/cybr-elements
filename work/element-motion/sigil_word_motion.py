"""Shared authored sigil path; independent from material/solver parameters."""
from pathlib import Path
import os,numpy as np
from scipy.ndimage import gaussian_filter1d
VARIANT=os.environ.get('SIGIL_STYLE','01');assert VARIANT in ['01','02']
with np.load(Path(__file__).resolve().parent/f'sigil-native/mark-{VARIANT}-motion.npz') as a:P=a['points'];T=a['times'];E=a['emit'];IDS=a['stroke_ids']
T=.15+(T-.15)/(T[-1]-.15)*5.05
MODE='arc';START=.15;WRITE=5.05
V=np.zeros_like(P);OMEGA=np.zeros(len(P))
for k in np.unique(IDS[IDS>=0]):
 ids=np.flatnonzero(IDS==k)
 if len(ids)<2:continue
 v=np.gradient(P[ids],T[ids],axis=0);v=gaussian_filter1d(v,.8,axis=0);speed=np.linalg.norm(v,axis=1);v*=np.minimum(1,9/np.maximum(speed,1e-6))[:,None];V[ids]=v
 angle=np.unwrap(np.arctan2(v[:,1],v[:,0]));OMEGA[ids]=gaussian_filter1d(np.gradient(angle,T[ids]),2)
def pose(t):
 p=np.array([np.interp(t,T,P[:,i]) for i in range(2)]);j=np.clip(np.searchsorted(T,t,side='right')-1,0,len(T)-1);v=V[j];speed=np.linalg.norm(v);direction=v/max(speed,1e-8)
 return p,direction,float(E[j]) if START<=t<=START+WRITE else 0.,float(speed)
def turn_rate(t):
 j=np.clip(np.searchsorted(T,t,side='right')-1,0,len(T)-1)
 return float(np.clip(OMEGA[j],-12,12)) if START<=t<=START+WRITE and E[j] else 0.
