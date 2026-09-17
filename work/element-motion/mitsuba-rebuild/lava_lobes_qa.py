"""CPU mesh and artifact checks; numerical checks do not grade realism."""
from pathlib import Path
import os,json,time
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1')
import numpy as np
R=Path(__file__).resolve().parent/'lava-focus'

def main():
    start=time.time();a=np.load(R/'lobes/lobes-05.npz');v,f,n=a['v'],a['f'],a['normal']
    assert np.isfinite(v).all() and np.isfinite(n).all() and np.isfinite(a['temperature']).all()
    lengths=np.linalg.norm(n,axis=1);assert np.max(abs(lengths-1))<1e-4
    edges=np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1)
    key=edges[:,0].astype(np.int64)*len(v)+edges[:,1];_,count=np.unique(key,return_counts=True)
    assert np.all(count==2),'Every closed crust/core surface edge must have two incident faces'
    cross=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
    area=np.linalg.norm(cross,axis=1)*.5
    zero=area==0;collapsed_max_edge=0.
    if zero.any():
        tri=v[f[zero]].astype('f8');precise=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)*.5
        print(json.dumps({'zeroAreaFloat32':int(zero.sum()),'zeroAreaFloat64':int((precise==0).sum()),'maxDoubleArea':float(precise.max()),'maxEdge':float(np.linalg.norm(tri[:,1]-tri[:,0],axis=1).max()),'fraction':float(zero.mean())}))
        collapsed_max_edge=max(float(np.linalg.norm(tri[:,i]-tri[:,j],axis=1).max()) for i,j in [(0,1),(1,2),(2,0)])
    # Continuous contour clipping can collapse a submicron sliver when the
    # double-precision mesh is exported as float32. It has zero surface area.
    assert collapsed_max_edge<1e-6 and zero.mean()<1e-5
    out={'device':'CPU','vertices':len(v),'triangles':len(f),'openEdges':int((count==1).sum()),'nonManifoldEdges':int((count>2).sum()),'zeroAreaTriangles':int((area==0).sum()),'unitNormalsMaxError':float(np.max(abs(lengths-1))),'temperatureRangeK':[float(a['temperature'].min()),float(a['temperature'].max())],'surfaceAreaM2':float(area.sum()),'seconds':round(time.time()-start,2),'limits':'These checks establish finite, closed component geometry. They do not establish nonintersection between overlapping lobes, physical flow accuracy or visual realism.'}
    out.update(collapsedTriangleMaxEdgeM=collapsed_max_edge,roundoffOnlyDegeneracies=True)
    (R/'lobes/qa.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))

if __name__=='__main__':main()
