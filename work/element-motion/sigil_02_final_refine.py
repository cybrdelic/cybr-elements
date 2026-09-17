from pathlib import Path
import numpy as np
from scipy.ndimage import map_coordinates
R=Path(__file__).resolve().parent;O=R/'sigil-02-elements'
with np.load(R/'sigil-02-v2/source.npz') as a:fields={k:a[k] for k in a.files}
def sample(name,x,z):return map_coordinates(fields[name],[(np.asarray(z)+1.05)/7.875*503,(np.asarray(x)+7)/14*895],order=1)
rng=np.random.default_rng(211);x=rng.uniform(-4,4,60000);z=rng.uniform(.65,3.25,60000);sd=sample('sdf',x,z);ok=sd>.009;x=x[ok];z=z[ok];sd=sd[ok]
centers=[];radii=[]
for tier,limit in [(0,230),(1,670)]:
 for i in rng.permutation(len(x)):
  d=sd[i]
  if tier==0 and d<.035:continue
  r=min(.24,max(.095,d*1.2))*rng.uniform(.85,1.1) if tier==0 else rng.uniform(.037,.073)
  c=np.array([x[i],rng.uniform(-.32,.32),z[i]])
  if centers and np.any(np.linalg.norm(np.asarray(centers)-c,axis=1)<np.asarray(radii)+r+.001):continue
  centers.append(c);radii.append(r)
  if len(centers)>=limit:break
c=np.asarray(centers);r=np.asarray(radii);b=sample('arrival',c[:,0],c[:,2]);d=np.column_stack((sample('dirx',c[:,0],c[:,2]),np.zeros(len(c)),sample('dirz',c[:,0],c[:,2])))
np.savez_compressed(O/'earth-source-v3.npz',centers=c,radii=r,births=b,directions=d)
s=(R/'sigil_02_earth_sim_v2.py').read_text().replace('earth-source-v2','earth-source-v3').replace('earth-motion-v2','earth-motion-v3').replace('earth-sim-report-v2','earth-sim-report-v3');(R/'sigil_02_earth_sim_v3.py').write_text(s)
s=(R/'sigil_02_earth_render_v2.py').read_text().replace('earth-frames-v2','earth-frames-v3').replace('earth-motion-v2','earth-motion-v3').replace('earth-pilot-v2','earth-pilot-v3');(R/'sigil_02_earth_render_v3.py').write_text(s)
# Lighter tracer supply and faster constant physical mist loss. This alters
# concentration in the transported field, never the composited image opacity.
s=(R/'sigil_02_air.py').read_text().replace('air-frames','air-frames-v2').replace('air-02.mp4','air-02-v2.mp4').replace('air-report.json','air-report-v2.json').replace('continue-air','continue-air-v2')
s=s.replace('torch.ones_like(soot)*.85','torch.ones_like(soot)*.55').replace('soot.mul_(math.exp(-.65*dt))','soot.mul_(math.exp(-1.35*dt))')
(R/'sigil_02_air_v2.py').write_text(s)
print('Earth bodies:',len(r),'median radius:',float(np.median(r)),'largest:',float(r.max()),'; lighter air field prepared')
