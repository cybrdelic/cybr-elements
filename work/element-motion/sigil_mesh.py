"""Streaming reconstruction with persistent classification and motion vectors."""
import os,sys,json,gzip,time,gc
from pathlib import Path
for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS']:os.environ[name]='2'
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R.parent/'flip-lettering/vendor/tools'))
import numpy as np
from scipy.spatial import cKDTree
from bending_surface import DetailReconstruction,encode
from bending_spray_v5 import Spray
variant=sys.argv[1];assert variant in ['01','02'];B=R/f'sigil-v1/water-{variant}';source=B/'particles';out=B/'meshes';out.mkdir(parents=True,exist_ok=True)
full=True;frames=range(300)
started=time.time();isolated=np.empty(0,bool);previous_iso=1.8
spray=None
for f in frames:
 if full:
  while len(list(out.glob('*.mesh.gz')))>=3:time.sleep(.5)
 while True:
  try:m=json.loads((source/'manifest.json').read_text());info=m['frames'][f];break
  except (OSError,json.JSONDecodeError,IndexError):time.sleep(.4)
 n=info['particles'];raw=np.frombuffer(gzip.decompress((source/f'{f:04}.gz').read_bytes()),'<f4')
 p=raw[:n*3].reshape(-1,3);v=raw[n*3:].reshape(-1,3);extent=np.array(m['config']['extent']);h=m['config']['h']
 if n>4:
  origin=np.maximum(0,np.floor((p.min(0)-5*h)/h)*h);upper=np.minimum(extent,np.ceil((p.max(0)+5*h)/h)*h)
  config=dict(m['config']);config['extent']=(upper-origin).tolist();config['surfaceOptions']={'spacingFactor':.43,'kernelRadiusFactor':1.48,'fieldSigma':.68,'meshSmoothingPasses':12}
  rec=DetailReconstruction(config);rec.isolated=isolated;rec.previous_iso=previous_iso
  history=np.zeros((n,6),np.float32);history[:,:3]=1
  field,velocity,verts,normals,faces,drops,radii,dv,iso,measure=rec.reconstruct(p-origin,v,history,[],m['frameDt'])
  isolated=rec.isolated.copy();previous_iso=iso
  verts+=origin;drops+=origin
  if spray is None:spray=Spray(h)
  drops,radii,dv,spray_stats=spray.step(p,v,isolated,m['frameDt'],rec.droplet_clusters)
  measure.update(spray_stats)
  # Transfer native particle velocities to the reconstructed moving surface.
  tree=cKDTree(p);dist,ids=tree.query(verts,k=min(6,n),workers=2)
  weight=1/np.maximum(dist,h*.07)**2;weight/=weight.sum(1)[:,None]
  vv=np.einsum('nk,nkj->nj',weight,v[ids]).astype(np.float32)
  del field,velocity,rec,history,tree,dist,ids,weight
 else:
  verts=normals=drops=vv=dv=np.empty((0,3),np.float32);faces=np.empty((0,3),np.uint32);radii=np.empty(0,np.float32);measure={}
 assert np.isfinite(verts).all() and np.isfinite(vv).all() and np.isfinite(p).all() and np.isfinite(v).all()
 if n>4 and abs(measure.get('totalRepresentedVolumeError',0))>.025:raise RuntimeError('Surface volume validation failed: '+str(measure['totalRepresentedVolumeError']))
 np.savez_compressed(out/f'{f:04}.velocity.npz',surface=vv,drops=dv,drop_positions=drops)
 (out/'manifest.json').write_text(json.dumps(m))
 row={'frame':f,'vertices':len(verts),'triangles':len(faces),'drops':len(drops),'persistentClassifier':True,'motionVectors':True,'seconds':round(time.time()-started,1),**measure}
 (out/f'{f:04}.json').write_text(json.dumps(row))
 encode(out/f'{f:04}.mesh.tmp',verts,normals,faces,drops,radii,np.empty((0,6),np.float32),p[::max(1,n//10000)],extent,np.zeros(len(verts),np.float32),np.zeros((1,1,2),np.uint8))
 (out/f'{f:04}.mesh.tmp').replace(out/f'{f:04}.mesh.gz')
 (source/f'{f:04}.gz').unlink()
 print('MESH',f,'verts',len(verts),'drops',len(drops),'seconds',round(time.time()-started,1),flush=True)
 del verts,normals,faces,drops,p,v,vv,dv;gc.collect()
print('MESH COMPLETE',flush=True)
