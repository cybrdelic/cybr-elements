"""Reduced 2D pressure field and Lagrangian tracers, CPU only.

Sound uses a damped acoustic wave equation. Pressure uses a localized inward
body-force pulse and rebound. These are deliberately slowed visual witnesses,
not calibrated real-time acoustics or a full compressible fluid solver.
"""
from pathlib import Path
import sys,json,numpy as np
from scipy.ndimage import map_coordinates
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R.parent));from shared_motion import pose
out=R/'cpu/witness';out.mkdir(exist_ok=True,parents=True)
nx,nz=160,112;dx=.05;dt=1/180;c=2.7
gx=np.arange(nx)*dx-3.55;gz=np.arange(nz)*dx-.55;X,Z=np.meshgrid(gx,gz);rng=np.random.default_rng(94)
N=24000;rest=np.c_[rng.uniform(-3.4,4.2,N),rng.normal(0,.028,N),rng.uniform(-.35,4.7,N)];radius=rng.uniform(.0008,.0022,N)
for kind in ['sound','pressure']:
 p=rest.copy();v=np.zeros_like(p);h=np.zeros((nz,nx));old=h.copy();history=[];values=[];speed=[];stats=[]
 for f in range(120):
  for sub in range(6):
   t=(f+(sub+1)/6)/30;em,_,on,_=pose(min(t,1.68));cx,cz=em
   if kind=='sound':
    lap=(np.roll(h,1,0)+np.roll(h,-1,0)+np.roll(h,1,1)+np.roll(h,-1,1)-4*h)/dx**2
    src=np.exp(-((X-cx)**2+(Z-cz)**2)/(.085**2))*np.sin(t*32)*on*13
    new=2*h-old+(c*dt)**2*lap+src*dt**2-.8*dt*(h-old);new[:3]*=.65;new[-3:]*=.65;new[:,:3]*=.65;new[:,-3:]*=.65;old,h=h,new
    zz,xx=np.gradient(h,dx);coords=np.array([(p[:,2]-gz[0])/dx,(p[:,0]-gx[0])/dx]);force=np.c_[-map_coordinates(xx,coords,order=1,mode='constant'),np.zeros(N),-map_coordinates(zz,coords,order=1,mode='constant')]*60
    force-=(p-rest)*8+v*1.2
   else:
    # Finite pulse pulls a seeded volume toward the moving pressure minimum;
    # the sign reverses briefly to expose rebound rather than fading opacity.
    center=np.array([cx,0,cz]);delta=p-center;distance=np.linalg.norm(delta,axis=1);pulse=np.exp(-((t-1.05)/.40)**2)-.65*np.exp(-((t-1.75)/.25)**2)
    force=-delta*(20*pulse*np.exp(-(distance/.72)**2))[:,None]-v*1.4
   v+=force*dt;p+=v*dt
  dist=np.linalg.norm(p-rest,axis=1);history.append(p.astype('f4'));values.append(dist.astype('f4'));speed.append(np.linalg.norm(v,axis=1).astype('f4'));stats.append(float(np.max(np.abs(h))))
 assert np.isfinite(history).all();np.savez_compressed(out/f'{kind}.npz',p=history,displacement=values,speed=speed,r=radius,rest=rest)
 (out/f'{kind}.json').write_text(json.dumps({'device':'CPU','particles':N,'frames':120,'grid':[nx,nz],'dt':dt,'CFL':c*dt/dx,'peakDisplacement':float(np.max(values)),'peakSpeed':float(np.max(speed)),'mechanism':'Damped traveling acoustic pressure' if kind=='sound' else 'Localized inward force and rebound','limits':'Two-dimensional slowed witness; pressure effect is a prescribed body force'},indent=2));print(kind,'CPU witness',round(float(np.max(values)),4),'max displacement')
