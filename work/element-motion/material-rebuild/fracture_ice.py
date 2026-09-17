"""Closed Voronoi cuts through the frozen carrier, preserving its outer surface."""
from pathlib import Path
import numpy as np,json,time,psutil
from scipy.cluster.vq import kmeans2
import manifold3d as mf
R=Path(__file__).resolve().parent
while psutil.virtual_memory().available<.8e9:time.sleep(10)
a=np.load(R/'data/ice/0050.npz');v=a['v'].copy();f=a['f'].copy()
if np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))<0:f=f[:,[0,2,1]]
body=mf.Manifold(mf.Mesh(v.astype('f4'),f.astype('u4')))
assert str(body.status()).endswith('NoError'),body.status()
# Keep connected bulk and meaningful chips; exclude isolated subpixel noise.
components=[x for x in body.decompose() if x.volume()>1e-5];body=mf.Manifold.compose(components)
np.random.seed(301);seeds,_=kmeans2(v[::3],36,minit='++',iter=30);pieces=[]
for i,seed in enumerate(seeds):
 piece=body
 for j in np.argsort(np.linalg.norm(seeds-seed,axis=1))[1:]:
  direction=seed-seeds[j];direction/=np.linalg.norm(direction);mid=(seed+seeds[j])*.5
  piece=piece.trim_by_plane(direction,float(mid@direction))
  if piece.is_empty():break
 for component in piece.decompose():
  if component.volume()<3e-5:continue
  mesh=component.to_mesh();vertices=mesh.vert_properties[:,:3].astype('f4');faces=mesh.tri_verts.astype('i4');center=vertices.mean(0);local=vertices-center
  pieces.append({'vertices':local.tolist(),'faces':faces.tolist(),'center':center.tolist(),'volume':float(component.volume())})
assert 20<len(pieces)<250
(R/'ice-fractures.json').write_text(json.dumps({'freezeFrame':50,'pieces':pieces,'sourceVolume':body.volume(),'pieceVolume':sum(p['volume'] for p in pieces),'method':__doc__},separators=(',',':')))
print('Closed ice fracture pieces',len(pieces),'volume coverage',round(sum(p['volume'] for p in pieces)/body.volume(),4),flush=True)
