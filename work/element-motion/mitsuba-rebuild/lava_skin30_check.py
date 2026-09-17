"""CPU finite-volume reference and GPU-kernel-on-CPU thermal verification."""
import os
from pathlib import Path
ROOT=Path(__file__).parent/'lava-focus/mpm/rebuild-30'
(ROOT/'temp').mkdir(parents=True,exist_ok=True)
os.environ.update(TEMP=str(ROOT/'temp'),TMP=str(ROOT/'temp'))
import numpy as np,json
import warp as wp
wp.config.kernel_cache_dir=str(ROOT.parent/'rebuild-28/warp-cache');wp.config.use_precompiled_headers=False
from lava_skin30 import surface_heat

def temp(h):return np.where(h<0,1173.15+h/1200,np.where(h<700000,1173.15+h/2800,1423.15+(h-700000)/1200))
def reference(n,dt):
    pitch=.0035;a=pitch**2;v=pitch**3;dx=.4*pitch/n;profile=np.full(n,732220.);mean=732220.;loss=0.
    for _ in range(round(1/dt)):
        t=temp(profile);core=float(temp((mean*v-a*dx*profile.sum())/(v-a*n*dx)))
        q=.94*5.670374419e-8*(t[0]**4-293.15**4)+12*(t[0]-293.15)
        f=np.zeros(n);flux=1.6*np.diff(t)/dx;f[:-1]+=flux;f[1:]-=flux;f[0]-=q;f[-1]+=1.6*(core-t[-1])/(1.5*dx)
        profile+=dt*f/(2700*dx);mean-=dt*q*a/(2700*v);loss+=dt*q*a
    return float(temp(profile[0])),mean,loss

wp.init()
with wp.ScopedDevice('cpu'):
    pitch=.0035;vol=pitch**3;area=pitch**2;dt=.002
    h=wp.full(1,732220.);hn=wp.empty_like(h);skin=wp.full((1,16),732220.);sn=wp.empty_like(skin);a=wp.full(1,area);loss=wp.zeros(1);ts=wp.zeros(1);energy=0.
    for _ in range(500):
        bulk=float(temp(float(h.numpy()[0])));power=area*(.94*5.670374419e-8*(bulk**4-293.15**4)+12*(bulk-293.15))
        hn.assign(np.array([float(h.numpy()[0])-power*dt/(2700*vol)],dtype='f4'));loss.fill_(power*dt)
        wp.launch(surface_heat,1,inputs=[h,hn,skin,sn,a,loss,ts,pitch,dt]);h,hn=hn,h;skin,sn=sn,skin;energy+=float(loss.numpy()[0])
    r16=reference(16,.0005);r32=reference(32,.000125)
    result=dict(surfaceTemperatureK=float(ts.numpy()[0]),cpuReference16=r16,cpuReference32=r32,kernelErrorK=abs(float(ts.numpy()[0])-r16[0]),refinementErrorK=abs(r16[0]-r32[0]),energyBalanceJ=abs((float(h.numpy()[0])-732220)*2700*vol+energy))
    result['passed']=bool(result['kernelErrorK']<.5 and result['refinementErrorK']<12 and result['energyBalanceJ']<.02 and 293<float(ts.numpy()[0])<1450)
    (ROOT/'skin-cpu-check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));raise SystemExit(not result['passed'])
