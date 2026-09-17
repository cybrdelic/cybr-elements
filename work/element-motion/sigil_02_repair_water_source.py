"""A pair of moving source fronts, with momentum; never a target for existing water."""
from pathlib import Path
import numpy as np,json
from scipy.ndimage import map_coordinates,distance_transform_edt
from skimage.morphology import medial_axis
R=Path(__file__).resolve().parent;O=R/'sigil-02-repair';O.mkdir(exist_ok=True)
src=dict(np.load(R/'sigil-02-v2/source.npz'));lo=src['lo'];ext=src['extent'];shape=src['sdf'].shape
skel,dist=medial_axis(src['sdf']>0,return_distance=True,rng=1871)
nearest=distance_transform_edt(~skel,return_distances=False,return_indices=True)
src['local_radius']=np.maximum(.025,dist[tuple(nearest)]*ext[0]/(shape[1]-1))
def sample(name,x,z):
 return map_coordinates(src[name],[(z-lo[2])/ext[2]*(shape[0]-1),(x-lo[0])/ext[0]*(shape[1]-1)],order=1,mode='constant',cval=-1 if name=='sdf' else 0)
rng=np.random.default_rng(80482);h=.018;scale=.35;origin=np.array([2.1,.98,.756]);spacing=h*.5/scale
x,z=np.meshgrid(np.arange(-4.02,4.03,spacing),np.arange(.50,3.41,spacing));x=x.ravel();z=z.ravel();d=sample('sdf',x,z);q=d>0;x=x[q];z=z[q];d=d[q]
sources=[]
local_radius=sample('local_radius',x,z)
for wave in range(1):
 for localy in np.arange(-.60,.601,spacing):
  # Circular cross-section: no constant-depth slab across wide strokes.
  depth=np.sqrt(np.maximum(0,d*(2*local_radius-d)))*1.1
  q=abs(localy)<depth
  a=x[q];b=z[q];sd=d[q]
  if not len(a):continue
  phase=a*2.1+b*1.7+wave*.65
  center=.20*np.sin(a*1.25)+.055*np.sin(phase)
  p=np.column_stack((a,b,np.full(len(a),localy)+center))+rng.uniform(-spacing*.18,spacing*.18,(len(a),3))
  t=.25+(sample('arrival',a,b)-.30)/3.60*1.5+wave*.70
  tx=sample('dirx',a,b);tz=sample('dirz',a,b);norm=np.maximum(np.hypot(tx,tz),.01);tx/=norm;tz/=norm
  # Curl within the cross-section and a depth-varying axial profile generate
  # shear/rolling in the pressure solve; no noise is added to the mesh later.
  speed=(.82+.24*(1-(localy/np.maximum(depth[q],.001))**2))*(1+.13*np.sin(a*5+b*3+wave))
  v=np.column_stack((tx*speed-tz*localy*1.1,tz*speed+tx*localy*1.1+.19,.20*np.cos(a*1.25)*tx+.08*np.cos(phase)))
  sources.append(np.column_stack((t,p*scale+origin,v)))
data=np.concatenate(sources);data=data[np.argsort(data[:,0])].astype('<f4');data.tofile(O/'water-source.f32')
report={'particles':len(data),'sourceStart':float(data[:,0].min()),'sourceEnd':float(data[:,0].max()),'sourceSpeedMedian':float(np.median(np.linalg.norm(data[:,4:],axis=1))),'h':h,'spaceScale':scale,'timeScale':.4,'origin':origin.tolist(),'source':'Full02 variable-radius round streams, medial radius sets actual thickness; one rapid advancing source and free momentum. No forces attract existing water to glyph.'}
(O/'water-source-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
