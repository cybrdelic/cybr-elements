"""CPU enthalpy columns deep enough for an old insulating lava crust.

Radiation, convection, internal conduction and the hot lower boundary are
bookkept. Initial surface ages are authored material history, not elapsed
shot time. No artificial heat extraction term is applied in these columns.
"""
import numpy as np
from numba import njit
from lava_skin import phase

@njit(cache=True)
def columns(age,bulk):
 n=len(age);layers=64;dz=.0006;rho=2700.;dtmax=.075
 skin=np.empty(n);removed=0.;received=0.;change=0.
 for i in range(n):
  h=np.full(layers,796000.);temperature=np.full(layers,1480.);t=0.
  while t<age[i]:
   dt=min(dtmax,age[i]-t);t+=dt
   for j in range(layers):temperature[j]=phase(h[j])[0]
   q=(.94*5.670374419e-8*(temperature[0]**4-293.15**4)+45*(temperature[0]-293.15))*dt
   h[0]-=q/(rho*dz);removed+=q
   for j in range(layers-1):
    q=1.6*(temperature[j+1]-temperature[j])/dz*dt/(rho*dz);h[j]+=q;h[j+1]-=q
   core=1480.+(bulk[i]-1480.)*t/age[i];q=1.6*(core-temperature[-1])/dz*dt;h[-1]+=q/(rho*dz);received+=q
  skin[i]=phase(h[0])[0];change+=(h.sum()-layers*796000.)*rho*dz
 return skin,abs(change+removed-received)/max(removed,1.)
