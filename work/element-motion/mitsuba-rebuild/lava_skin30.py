"""Conservative particle mean heat with a resolved 1D radiating skin closure.

The skin occupies at most 45% of a particle's volume. Core enthalpy is
reconstructed from the mean and skin so the skin is not additional mass.
This is a subgrid thermal model, not a new mechanical fracture solver.
"""
import warp as wp
from lava_newton28_thermal import temperature

@wp.kernel
def surface_heat(h:wp.array[float],hn:wp.array[float],skin:wp.array2d[float],sn:wp.array2d[float],area:wp.array[float],loss:wp.array[float],ts:wp.array[float],pitch:float,dt:float):
    p=wp.tid();vol=pitch*pitch*pitch;rho=2700.0;k=1.6;ambient=293.15;eps=.94;sigma=5.670374419e-8
    a=area[p];bulk=temperature(h[p]);n=16
    if a<.001*pitch*pitch:
        for j in range(16):sn[p,j]=hn[p]
        ts[p]=temperature(hn[p])
    else:
        length=wp.min(.4*pitch,.45*vol/a);dx=length/float(n)
        oldpower=a*(eps*sigma*(wp.pow(bulk,4.0)-wp.pow(ambient,4.0))+12.0*(bulk-ambient))
        # The 3D kernel already accounted for mean-temperature radiation;
        # replace that boundary flux, preserving its conduction and bed flux.
        external=(hn[p]-h[p]+oldpower*dt/(rho*vol))/4.0
        mean_h=h[p];radiation=float(0.0);sub_dt=dt/4.0
        for sub in range(4):
            total=float(0.0)
            for j in range(16):total+=skin[p,j]
            core_h=(mean_h*vol-a*dx*total)/(vol-a*length)
            core_t=temperature(core_h)
            surf=temperature(skin[p,0]);power=a*(eps*sigma*(wp.pow(surf,4.0)-wp.pow(ambient,4.0))+12.0*(surf-ambient))
            for j in range(16):
                t=temperature(skin[p,j]);flux=float(0.0)
                if j==0:flux-=power/a
                else:flux+=k*(temperature(skin[p,j-1])-t)/dx
                if j==15:flux+=k*(core_t-t)/(1.5*dx)
                else:flux+=k*(temperature(skin[p,j+1])-t)/dx
                sn[p,j]=skin[p,j]+sub_dt*flux/(rho*dx)
            for j in range(16):skin[p,j]=sn[p,j]
            mean_h+=external-power*sub_dt/(rho*vol);radiation+=power*sub_dt
        hn[p]=mean_h;loss[p]+=radiation-oldpower*dt
        ts[p]=temperature(sn[p,0])
