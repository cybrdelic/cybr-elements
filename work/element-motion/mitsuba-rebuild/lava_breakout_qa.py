"""CPU integrity checks for the rupture study, not a realism score."""
from pathlib import Path
import os,json,time,argparse,hashlib
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1')
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

R=Path(__file__).resolve().parent/'lava-focus'

def main(name,folder='breakout'):
    start=time.time();path=R/folder/f'{name}.npz';a=np.load(path)
    v,f,n=a['v'],a['f'],a['normal']
    assert all(np.isfinite(a[k]).all() for k in ['v','normal','rest','temperature'])
    assert f.min()>=0 and f.max()<len(v)
    error=float(np.max(abs(np.linalg.norm(n,axis=1)-1)));assert error<1e-4
    edges=np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1)
    unique,counts=np.unique(edges[:,0].astype('i8')*len(v)+edges[:,1],return_counts=True)
    assert np.all(counts==2),'Open or nonmanifold edge'
    triangles=v[f].astype('f8');area=.5*np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]),axis=1)
    degenerate=area==0;max_edge=0.
    if degenerate.any():
        t=triangles[degenerate];max_edge=max(float(np.linalg.norm(t[:,i]-t[:,j],axis=1).max()) for i,j in [(0,1),(1,2),(2,0)])
    assert max_edge<1e-6 and degenerate.mean()<1e-5
    core=a['component']==0;core_f=f[core[f].all(1)];used,ix=np.unique(core_f,return_inverse=True);cf=ix.reshape(-1,3)
    e=np.r_[cf[:,[0,1]],cf[:,[1,2]],cf[:,[2,0]]]
    adj=coo_matrix((np.ones(len(e),'u1'),(e[:,0],e[:,1])),shape=(len(used),len(used))).tocsr()
    connected=int(connected_components(adj,directed=False,return_labels=False));assert connected==1
    signed_volume=float(np.sum(triangles[:,0]*np.cross(triangles[:,1],triangles[:,2]))/6)
    assert signed_volume>0
    output={'device':'CPU','source':str(path),'sourceSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'vertices':len(v),'triangles':len(f),'coreConnectedComponents':connected,'openEdges':int((counts==1).sum()),'nonManifoldEdges':int((counts>2).sum()),'zeroAreaTriangles':int(degenerate.sum()),'collapsedTriangleMaxEdgeM':max_edge,'normalMaxError':error,'temperatureRangeK':[float(a['temperature'].min()),float(a['temperature'].max())],'seconds':round(time.time()-start,2),'limits':'Checks finite closed geometry and one connected core. Does not validate collision-free crust, fluid dynamics, temporal coherence, or visual realism.'}
    (R/folder/f'{name}-qa.json').write_text(json.dumps(output,indent=2));print(json.dumps(output))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',default='rupture-03');p.add_argument('--folder',choices=['breakout','crust-volume'],default='breakout');args=p.parse_args();main(args.source,args.folder)
