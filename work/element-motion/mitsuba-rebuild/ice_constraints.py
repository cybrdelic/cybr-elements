"""A brittle XPBD solid network activated by the resolved freezing fraction.

Bond rest lengths are recorded at solidification, not at an arbitrary frame.
Cold bonds contract thermally and break irreversibly in tension. Compliance
is derived from a Young modulus and bond area. This graph approximation
does not resolve continuum fracture toughness or crack-tip singularities.
"""
import numpy as np
from numba import njit
from scipy.spatial import cKDTree

def network(rest,birth,radius=.14):
 pairs=cKDTree(rest).query_pairs(radius,output_type='ndarray')
 pairs=pairs[np.abs(birth[pairs[:,0]]-birth[pairs[:,1]])<.065]
 return pairs.astype('i4'),np.zeros(len(pairs)),np.zeros(len(pairs),dtype='i1'),np.zeros(len(pairs)),np.zeros(len(pairs))

@njit(cache=True)
def advance(x,v,temperature,phase,pairs,length,status,freeze_temp,peak_strain,mass,dt,iterations=12):
 old=x.copy();young=9e9;area=(mass/917.)**(2/3)*.12;compliance=1/(young*area);lambdas=np.zeros(len(pairs));broken=0
 for b in range(len(pairs)):
  i,j=pairs[b]
  if status[b]==0 and min(phase[i],phase[j])>.80:
   length[b]=np.sqrt(np.sum((x[i]-x[j])**2));freeze_temp[b]=(temperature[i]+temperature[j])*.5;status[b]=1
 for it in range(iterations):
  for b in range(len(pairs)):
   if status[b]!=1:continue
   i,j=pairs[b];delta=x[i]-x[j];distance=np.sqrt(np.sum(delta*delta));target=length[b]*(1+5e-5*((temperature[i]+temperature[j])*.5-freeze_temp[b]));strain=(distance-target)/max(target,1e-8);peak_strain[b]=max(peak_strain[b],strain)
   # The first iteration sees the predictor strain before hard projection.
   # This macroscopic graph uses a regularized strain threshold, not a
   # claim that the ice fracture toughness has been calibrated.
   if it==0 and strain>.012:status[b]=2;broken+=1;continue
   alpha=compliance*target/(dt*dt);dl=(-(distance-target)-alpha*lambdas[b])/(2/mass+alpha);lambdas[b]+=dl;correction=dl/mass*delta/max(distance,1e-12);x[i]+=correction;x[j]-=correction
 v+=(x-old)/dt
 return broken
