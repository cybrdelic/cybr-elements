from pathlib import Path
import numpy as np,json
from scipy.ndimage import map_coordinates
R=Path(__file__).resolve().parent;O=R/'sigil-02-elements'
with np.load(R/'sigil-02-v2/source.npz') as a:s={k:a[k] for k in a.files}
rng=np.random.default_rng(9194)
def field(name,x,z):return map_coordinates(s[name],[(np.asarray(z)+1.05)/7.875*503,(np.asarray(x)+7)/14*895],order=1)
xs=rng.uniform(-4,4,50000);zs=rng.uniform(.65,3.25,50000);sd=field('sdf',xs,zs);use=sd>.008;xs=xs[use];zs=zs[use];sd=sd[use]
centers=[];radii=[]
for k,(x,z,d) in enumerate(zip(xs,zs,sd)):
 radius=min(.21,.036/max(.06,rng.random())**.6)
 radius=min(radius,max(.038,d*.95))
 depth=min(.27,np.sqrt(d*.35));c=np.array([x,rng.uniform(-depth,depth)+.05*np.sin(x*3),z])
 if centers and np.any(np.linalg.norm(np.asarray(centers)-c,axis=1)<np.asarray(radii)+radius+.001):continue
 centers.append(c);radii.append(radius)
 if len(centers)>=1350:break
c=np.asarray(centers);r=np.asarray(radii);b=field('arrival',c[:,0],c[:,2]);d=np.column_stack((field('dirx',c[:,0],c[:,2]),np.zeros(len(c)),field('dirz',c[:,0],c[:,2])))
np.savez_compressed(O/'earth-source-v2.npz',centers=c,radii=r,births=b,directions=d)
s=(R/'sigil_02_earth_sim.py').read_text().replace("'earth-source.npz'","'earth-source-v2.npz'").replace("'earth-motion.npz'","'earth-motion-v2.npz'").replace("'earth-sim-report.json'","'earth-sim-report-v2.json'").replace('p=target-direction*.28;p[:,1]-=.16','p=target-direction*.65;p[:,1]-=.55').replace('v=direction*1.3;v[:,1]=.7','v=direction*2.0;v[:,1]=1.1')
(R/'sigil_02_earth_sim_v2.py').write_text(s)
s=(R/'sigil_02_earth_render.py').read_text().replace("'earth-frames'","'earth-frames-v2'").replace("'earth-motion.npz'","'earth-motion-v2.npz'")
(R/'sigil_02_earth_render_v2.py').write_text(s)
print(json.dumps({'bodies':len(c),'radii':[float(r.min()),float(np.median(r)),float(r.max())],'improvement':'Larger layered clasts and deeper cross-section replace gravel-like point fill; stronger incoming inertia'}))
