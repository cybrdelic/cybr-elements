from pathlib import Path
import sys,math
import numpy as np
from scipy.ndimage import map_coordinates,gaussian_filter
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R.parent));from shared_motion import pose
nx,nz=240,120;x=np.linspace(-4.75,4.75,nx);z=np.linspace(-.35,4.35,nz);xx,zz=np.meshgrid(x,z);dx=x[1]-x[0];dt=1/240
for K in ['seismic','sound','heat']:
 h=np.zeros_like(xx);v=np.zeros_like(xx);temp=np.zeros_like(xx);frames=[]
 for f in range(120):
  for sub in range(8):
   t=(f+sub/8)/30;p,d,on,_=pose(t);r2=(xx-p[0])**2+(zz-p[1])**2
   if K=='heat':
    vx=.22*np.sin(zz*4-t*2)+.10*np.sin(xx*8+t*3);vz=.55+temp*.4;row,col=np.indices(temp.shape);temp=map_coordinates(temp,[row-vz*dt/dx,col-vx*dt/dx],order=1,mode='constant')
    if .08<t<1.68:temp+=np.exp(-r2/.026)*dt*18
    temp=gaussian_filter(temp,.12)*math.exp(-dt*.8);h=temp
   else:
    lap=(np.roll(h,1,0)+np.roll(h,-1,0)+np.roll(h,1,1)+np.roll(h,-1,1)-4*h)/dx**2;c=2.8 if K=='sound' else 1.5;v+=(c*c*lap-1.8*v)*dt
    if .08<t<1.68:v+=np.exp(-r2/(.028 if K=='sound' else .055))*math.sin(t*math.tau*(9 if K=='sound' else 4))*dt*(20 if K=='sound' else 12)
    h+=v*dt;h[:2]=0;h[-2:]=0;h[:,:2]=0;h[:,-2:]=0
  frames.append(h.astype('f4'))
 np.savez_compressed(R/f'{K}-waves.npz',height=frames,x=x,z=z)
 print(K,120,'integrated fields',flush=True)
