"""Volume-checked surface reconstruction of the newly solved material state."""
from pathlib import Path
import argparse,json,time,numpy as np
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree
from skimage.measure import marching_cubes
R=Path(__file__).resolve().parent

def reconstruct(kind,frame):
 start=time.time();a=np.load(R/'cache'/kind/f'{frame:04}.npz');p=a['p'];phase=a['phase'];spacing=.023;radius=.055;lo=np.floor((p.min(0)-radius*3)/spacing)*spacing;shape=np.ceil((p.max(0)+radius*3-lo)/spacing).astype(int)+1;assert np.prod(shape)<12000000;grid=np.zeros(shape,dtype='f4');q=(p-lo)/spacing;base=np.floor(q).astype(int);frac=q-base
 for i in [0,1]:
  for j in [0,1]:
   for k in [0,1]:
    index=base+[i,j,k];weight=(frac[:,0] if i else 1-frac[:,0])*(frac[:,1] if j else 1-frac[:,1])*(frac[:,2] if k else 1-frac[:,2]);np.add.at(grid,tuple(index.T),weight)
 grid=gaussian_filter(grid,radius/spacing,mode='constant');rho0=1000 if kind=='ice' else 2600;rho=(1-phase)*rho0+phase*(917 if kind=='ice' else 2800);target=float(np.sum(float(a['volume'])*rho0/rho));left=float(grid.max())*.002;right=float(grid.max())*.8;best=None
 for step in range(9):
  level=(left+right)/2;v,f,_,_=marching_cubes(grid,level=level,spacing=(spacing,)*3);v+=lo;signed=float(np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))/6)
  if signed<0:f=f[:,[0,2,1]]
  volume=abs(signed);best=(v,f,volume,level)
  if volume>target:left=level
  else:right=level
 v,f,volume,level=best;distance,ix=cKDTree(p).query(v,k=4,workers=1);w=1/np.maximum(distance,.004)**3;w/=w.sum(1)[:,None];fields={}
 for name in ['temperature','phase','damage','birth']:
  fields[name]=(a[name][ix]*w).sum(1).astype('f4')
 fields['deformation']=(a['F'][ix]*w[...,None,None]).sum(1).astype('f4')
 fields['rest']=(a['rest'][ix]*w[...,None]).sum(1).astype('f4');normal=np.zeros_like(v);fn=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
 for j in range(3):np.add.at(normal,f[:,j],fn)
 normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-12);out=R/'mesh'/kind;out.mkdir(parents=True,exist_ok=True);np.savez_compressed(out/f'{frame:04}.npz',v=v.astype('f4'),f=f.astype('i4'),normal=normal.astype('f4'),**fields)
 edges=np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1);_,counts=np.unique(edges,axis=0,return_counts=True);report={'kind':kind,'frame':frame,'vertices':len(v),'triangles':len(f),'volume':volume,'targetVolume':target,'relativeVolumeError':abs(volume/target-1),'boundaryEdges':int((counts==1).sum()),'nonmanifoldEdges':int((counts>2).sum()),'grid':shape.tolist(),'seconds':round(time.time()-start,3),'note':'Adaptive isovalue preserves the thermal phase-density volume; this does not certify the underlying flow model.'};assert report['relativeVolumeError']<.045 and not report['boundaryEdges'] and not report['nonmanifoldEdges'],report;(out/f'{frame:04}.json').write_text(json.dumps(report,indent=2));print('SURFACE',json.dumps(report))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--kind',required=True);ap.add_argument('--frame',type=int,default=61);a=ap.parse_args();reconstruct(a.kind,a.frame)
