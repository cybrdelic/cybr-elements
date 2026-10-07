"""Add lamina coordinates to source leaves without changing any geometry."""
from pathlib import Path
import numpy as np,json,hashlib
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
P=Path(__file__).resolve().parents[2]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/objects/forest-tree'
v=np.fromfile(P/'vertices.bin',dtype='<f4').reshape(-1,9);f=np.fromfile(P/'indices.bin',dtype='<u4').reshape(-1,3)
ids=np.flatnonzero(v[:,8]>7.5);remap=np.full(len(v),-1);remap[ids]=np.arange(len(ids));faces=remap[f[v[f[:,0],8]>7.5]]
edges=np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]);graph=coo_matrix((np.ones(len(edges),bool),(edges[:,0],edges[:,1])),shape=(len(ids),len(ids))).tocsr()
n,label=connected_components(graph,directed=False);order=np.argsort(label);cuts=np.r_[0,np.flatnonzero(np.diff(label[order]))+1,len(order)]
for a,b in zip(cuts[:-1],cuts[1:]):
    vi=ids[order[a:b]];points=v[vi,:3];points=points-points.mean(0);_,_,axes=np.linalg.svd(points,full_matrices=False);uv=points@axes[:2].T
    uv=(uv-uv.min(0))/np.maximum(np.ptp(uv,axis=0),1e-9)
    v[vi,6:8]=uv
v.astype('<f4').tofile(P/'vertices.bin')
m=json.loads((P/'manifest.json').read_text());m['leafCoordinates']={'leaves':int(n),'method':'Principal lamina coordinates for each connected source leaf; no vertex positions or topology changed'}
m['files']['vertices.bin']['sha256']=hashlib.sha256((P/'vertices.bin').read_bytes()).hexdigest();(P/'manifest.json').write_text(json.dumps(m,indent=2))
print(json.dumps(m['leafCoordinates']))
