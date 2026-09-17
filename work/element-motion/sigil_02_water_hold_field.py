"""Final bounded physics correction: do not squeeze the liquid inside its source volume."""
from pathlib import Path
import json,numpy as np
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent;O=R/'sigil-02-water-hold';out=O/'field-correction';out.mkdir(exist_ok=True)
c=json.loads((O/'config.json').read_text());g=np.load(O/'guides.npz');p=g['points'];radius=g['radii'];tree=cKDTree(p)
shape=(c['nx']+1,c['ny']+1,c['nz']+1);grid=np.indices(shape,dtype=np.float32).reshape(3,-1).T
for axis in range(3):
 result=np.empty((len(grid),2),np.float32);offset=np.full(3,.5);offset[axis]=0
 for begin in range(0,len(grid),5000):
  xyz=(grid[begin:begin+5000]+offset)*c['h'];dist,ids=tree.query(xyz,k=16,workers=2)
  # Use the union boundary, not the nearest centerline. At intersections the
  # nearest thin branch must not squeeze fluid that belongs to a wider one.
  sd=dist-radius[ids];winner=sd.argmin(axis=1);row=np.arange(len(xyz));which=ids[row,winner];d=dist[row,winner];r=radius[which]
  outside=np.maximum(0,sd[row,winner]);n=(xyz-p[which])/np.maximum(d[:,None],1e-8)
  band=np.exp(-np.maximum(0,outside/np.maximum(r,.02)-1.8)**2)
  result[begin:begin+len(xyz),0]=-160*outside*n[:,axis]*band
  result[begin:begin+len(xyz),1]=5*n[:,axis]**2*band
 result.tofile(out/f'guide-{axis}.f32')
 print('Union-boundary guide',axis,flush=True)
a=np.fromfile(O/'source.f32','<f4').reshape(-1,7).copy();a[:,4:]*=.3;a.tofile(out/'source.f32')
report=json.loads((O/'source-report.json').read_text());report.update(medianSpeed=float(np.median(np.linalg.norm(a[:,4:],axis=1))),forceBoundary='Union of variable-radius source tubes, zero force inside, exterior spring160, radial damping5',iteration=3,reason='CPU images revealed a persistent left breakup patch; previous field squeezed intersections and retained excessive input energy')
(out/'source-report.json').write_text(json.dumps(report,indent=2))
print('Final bounded correction ready',len(a),report['medianSpeed'])
