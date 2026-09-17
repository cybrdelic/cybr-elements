"""Emit disks normal to curved 3D jets, using the artwork's local stroke radius."""
from pathlib import Path
import json,numpy as np
from scipy.ndimage import map_coordinates,gaussian_filter1d
R=Path(__file__).resolve().parent;O=R/'sigil-02-repair';guides=json.loads((O/'lightning-guides.json').read_text());src=np.load(R/'sigil-02-v2/source.npz');lo=src['lo'];ext=src['extent'];shape=src['sdf'].shape
h=.018;scale=.35;origin=np.array([2.1,.98,.756]);spacing=h*.5/scale;rng=np.random.default_rng(6415);rows=[]
for index,g in enumerate(guides):
 p=np.asarray(g['points']);rad=np.asarray(g['widths']);length=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
 # Real depth travel, inherited as a component of the fluid velocity.
 p[:,1]=.38*np.sin(p[:,0]*1.10)+.09*np.sin(p[:,2]*3+p[:,0]*2)
 dist=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];samples=np.arange(0,dist[-1],spacing)
 path=np.column_stack([np.interp(samples,dist,p[:,k]) for k in range(3)]);radii=np.interp(samples,dist,rad)
 path=gaussian_filter1d(path,1.1,axis=0,mode='nearest');tangent=np.gradient(path,axis=0);tangent/=np.maximum(np.linalg.norm(tangent,axis=1)[:,None],1e-5)
 normal=np.cross(tangent,[0,1,0]);normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-5);binormal=np.cross(tangent,normal)
 for j,center in enumerate(path):
  radius=float(np.clip(radii[j]*.92,.035,.26));x,z=np.meshgrid(np.arange(-radius,radius+spacing/2,spacing),np.arange(-radius,radius+spacing/2,spacing));disk=np.column_stack((x.ravel(),z.ravel()));disk=disk[(disk**2).sum(1)<radius*radius]
  if not len(disk):continue
  pos=center+disk[:,:1]*normal[j]+disk[:,1:]*binormal[j]+rng.uniform(-spacing*.2,spacing*.2,(len(disk),3))
  coord=[[(center[2]-lo[2])/ext[2]*(shape[0]-1)],[(center[0]-lo[0])/ext[0]*(shape[1]-1)]]
  arrival=float(map_coordinates(src['arrival'],coord,order=1)[0]);birth=.25+(arrival-.30)/3.60*1.75
  speed=.82+.18*(1-(disk**2).sum(1)/(radius*radius));velocity=tangent[j]*speed[:,None]+(disk[:,:1]*binormal[j]-disk[:,1:]*normal[j])*1.5
  velocity[:,2]+=.12
  # Coordinate convention: solver uses x,height,depth.
  rows.append(np.column_stack((np.full(len(pos),birth),pos[:,[0,2,1]]*scale+origin,velocity[:,[0,2,1]])))
data=np.concatenate(rows);data=data[np.argsort(data[:,0])].astype('<f4');data.tofile(O/'water-source.f32')
report=dict(particles=len(data),nozzle='Round disks in the plane NORMAL to each 3D stream; variable radius from approved02; continuous tangential momentum',sourceSpeedMedian=float(np.median(np.linalg.norm(data[:,4:],axis=1))),sourceStart=float(data[:,0].min()),sourceEnd=float(data[:,0].max()),spaceScale=scale,timeScale=.4,origin=origin.tolist(),noSheetExtrusion=True,noTargetForces=True)
(O/'water-source-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
