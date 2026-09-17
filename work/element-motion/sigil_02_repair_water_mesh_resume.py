"""Streaming reconstruction with persistent classification and motion vectors."""
import os,sys,json,gzip,time,gc
from pathlib import Path
for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS']:os.environ[name]='2'
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R.parent/'flip-lettering/vendor/tools'))
import numpy as np
from scipy.spatial import cKDTree
from PIL import Image,ImageDraw
import cv2
from bending_surface import DetailReconstruction,encode
from mesh_cache import deposit,sample
from sigil_02_repair_spray import Spray
B=R/'sigil-02-repair';source=B/'water-particles';out=B/'water-mesh';out.mkdir(parents=True,exist_ok=True)
full=True;frames=range(192)
started=time.time();isolated=np.empty(0,bool);previous_iso=1.8
spray=None
for f in frames:
 pilot=not (B/'water-continue').exists()
 if full and not pilot:
  while len(list(out.glob('*.mesh.gz')))>=4:time.sleep(.5)
 while True:
  try:m=json.loads((source/'manifest.json').read_text());info=m['frames'][f];break
  except (OSError,json.JSONDecodeError,IndexError):time.sleep(.4)
 n=info['particles'];raw=np.frombuffer(gzip.decompress((source/f'{f:04}.gz').read_bytes()),'<f4')
 p=raw[:n*3].reshape(-1,3);v=raw[n*3:].reshape(-1,3);extent=np.array(m['config']['extent']);h=m['config']['h']
 if (B/'water-frames'/f'{f:04}.jpg').exists():
  # Rebuild only classifier/spray state during deterministic simulation replay.
  # The expensive surface and GPU image are retained exactly as rendered.
  if n>2048:
   lower=np.maximum(0,np.floor((p.min(0)-5*h)/h)*h);upper=np.minimum(extent,np.ceil((p.max(0)+5*h)/h)*h);spacing=h*.43
   gridShape=tuple(np.ceil((upper-lower)/spacing).astype(int)+1)
   rho,vx,vy,vz=deposit(p-lower,v,gridShape,spacing,h*.98);density=sample(rho,p-lower,spacing);del rho,vx,vy,vz
   if len(isolated)<n:isolated=np.pad(isolated,(0,n-len(isolated)))
   before=isolated.copy();isolated=np.zeros(n,bool);boundary=np.flatnonzero(density<3.55)
   if len(boundary):
    tree=cKDTree(p);dist,ids=tree.query(p[boundary],k=min(32,n),workers=1);counts=(dist<h).sum(1);isolated[boundary]=np.where(before[boundary],(density[boundary]<1.40)&(counts<7),(density[boundary]<1.16)&(counts<5));del tree,dist,ids
   if spray is None:spray=Spray(h)
   cluster=object.__new__(DetailReconstruction);cluster.h=h
   spray.step(p,v,isolated,m['frameDt'],cluster.droplet_clusters)
   old=out/f'{f:04}.json'
   if old.exists():previous_iso=json.loads(old.read_text()).get('isovalue',previous_iso)
  (source/f'{f:04}.gz').unlink()
  if f%15==0:print('REPLAY state',f,'seconds',round(time.time()-started,1),flush=True)
  continue
 if n:
  # CPU depth/speed preview is an explicit diagnostic, not the final render.
  xy=np.column_stack(((p[:,0]-m['origin'][0])/m['spaceScale'],(p[:,1]-m['origin'][1])/m['spaceScale']))
  uv=np.column_stack(((xy[:,0]/10.5+.5)*960,(.5-(xy[:,1]-1.8)/5.90625)*540)).astype(int)
  canvas=np.zeros((540,960,3),np.uint8);valid=(uv[:,0]>=0)&(uv[:,0]<960)&(uv[:,1]>=0)&(uv[:,1]<540)
  depth=p[:,2];order=np.argsort(depth)[::-1];col=np.column_stack((80+80*np.clip(depth/1.512,0,1),150+80*np.clip(depth/1.512,0,1),np.full(n,230))).astype(np.uint8)
  for i in order[valid[order]]:canvas[uv[i,1],uv[i,0]]=col[i]
  (B/'water-cpu').mkdir(exist_ok=True);Image.fromarray(canvas).save(B/'water-cpu'/f'{f:04}.jpg',quality=90)
 if pilot and f not in [24,45,66,87]:
  (source/f'{f:04}.gz').unlink();continue
 allp,allv=p,v;visibleIds=np.arange(n)
 if len(isolated)<n:isolated=np.pad(isolated,(0,n-len(isolated)))
 if f>135 and n>4:
  visibleIds=np.flatnonzero(p[:,1]>.12);p=p[visibleIds];v=v[visibleIds];n=len(p);isolated=isolated[visibleIds]

 if n>2048:
  origin=np.maximum(0,np.floor((p.min(0)-5*h)/h)*h);upper=np.minimum(extent,np.ceil((p.max(0)+5*h)/h)*h)
  config=dict(m['config']);config['extent']=(upper-origin).tolist();config['surfaceOptions']={'spacingFactor':.43,'kernelRadiusFactor':1.48,'fieldSigma':.48,'meshSmoothingPasses':6}
  rec=DetailReconstruction(config);rec.isolated=isolated;rec.previous_iso=previous_iso
  history=np.zeros((n,6),np.float32);history[:,:3]=1
  field,velocity,verts,normals,faces,drops,radii,dv,iso,measure=rec.reconstruct(p-origin,v,history,[],m['frameDt'])
  localIsolated=rec.isolated.copy();isolated=np.zeros(len(allp),bool);isolated[visibleIds]=localIsolated;previous_iso=iso
  verts+=origin;drops+=origin
  if spray is None:spray=Spray(h)
  drops,radii,dv,spray_stats=spray.step(allp,allv,isolated,m['frameDt'],rec.droplet_clusters)
  measure.update(spray_stats)
  # Transfer native particle velocities to the reconstructed moving surface.
  tree=cKDTree(p);dist,ids=tree.query(verts,k=min(6,n),workers=2)
  weight=1/np.maximum(dist,h*.07)**2;weight/=weight.sum(1)[:,None]
  vv=np.einsum('nk,nkj->nj',weight,v[ids]).astype(np.float32)
  del field,velocity,rec,history,tree,dist,ids,weight
 else:
  verts=normals=vv=np.empty((0,3),np.float32);faces=np.empty((0,3),np.uint32);drops=p.copy();dv=v.copy();radii=np.full(n,np.cbrt((h*.5)**3*3/(4*np.pi)),np.float32);measure={'sparseTail':True}
 assert np.isfinite(verts).all() and np.isfinite(vv).all()
 if n>4 and abs(measure.get('totalRepresentedVolumeError',0))>.025:raise RuntimeError('Surface volume validation failed: '+str(measure['totalRepresentedVolumeError']))
 np.savez_compressed(out/f'{f:04}.velocity.npz',surface=vv,drops=dv,drop_positions=drops)
 (out/'manifest.json').write_text(json.dumps(m))
 row={'frame':f,'vertices':len(verts),'triangles':len(faces),'drops':len(drops),'persistentClassifier':True,'motionVectors':True,'seconds':round(time.time()-started,1),**measure}
 (out/f'{f:04}.json').write_text(json.dumps(row))
 encode(out/f'{f:04}.mesh.tmp',verts,normals,faces,drops,radii,np.empty((0,6),np.float32),p[::max(1,n//10000)],extent,np.zeros(len(verts),np.float32),np.zeros((1,1,2),np.uint8))
 (out/f'{f:04}.mesh.tmp').replace(out/f'{f:04}.mesh.gz')
 if not pilot:(source/f'{f:04}.gz').unlink()
 print('MESH',f,'verts',len(verts),'drops',len(drops),'seconds',round(time.time()-started,1),flush=True)
 del verts,normals,faces,drops,p,v,vv,dv;gc.collect()
print('MESH COMPLETE',flush=True)
