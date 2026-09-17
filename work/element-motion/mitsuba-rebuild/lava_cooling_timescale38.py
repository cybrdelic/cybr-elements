"""Independent 1D conduction/enthalpy timescale screen, not a 3D lava cache.

Six millimetres of hot lava on twelve millimetres of finite cold rock.
Only the exposed top radiates/convects. This omits lateral cooling, feed,
deformation and gas transport, so it estimates a mechanism, not the shot.
"""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import json,time,numpy as np
from scipy.sparse import diags
from lava_mpm import Material,heat_solve,ROOT

def run(dx,dt,end=60.):
    count=round(.018/dx);z=(np.arange(count)+.5)*dx-.012;lava=z>0
    cp=np.where(lava,1200.,850.);rho=np.where(lava,2700.,2800.);k=np.where(lava,1.6,2.5)
    material=Material(cp=cp,latent_heat=np.where(lava,400000.,0.))
    mass=rho*dx;h=material.enthalpy(np.where(lava,1450.,293.15))
    conductance=2*k[1:]*k[:-1]/(k[1:]+k[:-1])/dx
    diagonal=np.r_[conductance,0]+np.r_[0,conductance]
    K=diags([-conductance,diagonal,-conductance],[-1,0,1],format='csr')
    area=np.zeros(count);area[-1]=1.;records=[];first_coherent=None;first_dark=None
    loss=0.;initial=mass@h;start=time.monotonic()
    for i in range(round(end/dt)):
        h,r=heat_solve(material,h,mass,K,area,293.15,dt)
        loss+=float(np.sum(r['radiation']+r['convection']))
        t=(i+1)*dt;temperature=material.temperature(h);solid=material.solid(temperature)
        if first_coherent is None and solid[-1]>=.65:first_coherent=t
        if first_dark is None and temperature[-1]<=1000:first_dark=t
        if abs(t-round(t))<1e-8:
            skin=0.
            for q in solid[lava][::-1]:
                if q<.65:break
                skin+=dx
            records.append(dict(time=t,topTemperatureK=float(temperature[-1]),bottomLavaTemperatureK=float(temperature[lava][0]),topCoherentSkinMm=skin*1000))
    balance=abs(float(mass@h-initial+loss))/max(abs(float(initial)),1.)
    assert balance<1e-7
    return dict(dx=dx,dt=dt,seconds=time.monotonic()-start,firstCoherentTopSeconds=first_coherent,firstTopBelow1000KSeconds=first_dark,relativeEnergyBalance=balance,records=records)

if __name__=='__main__':
    cases=[run(.00025,.05),run(.00025,.025),run(.000125,.025)]
    a,b,c=cases
    temporal=max(abs(x['topTemperatureK']-y['topTemperatureK']) for x,y in zip(a['records'],b['records']))
    spatial=max(abs(x['topTemperatureK']-y['topTemperatureK']) for x,y in zip(b['records'],c['records']))
    report=dict(scope=__doc__,cases=cases,maximumTopTemperatureChangeUnderTimeRefinementK=temporal,maximumTopTemperatureChangeUnderSpaceRefinementK=spatial)
    (ROOT/'rebuild-38/cooling-timescale.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(cases=[{k:v for k,v in q.items() if k!='records'} for q in cases],timeRefinementK=temporal,spaceRefinementK=spatial)))
