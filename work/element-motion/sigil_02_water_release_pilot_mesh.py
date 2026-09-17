"""Resolved native liquid surfaces. No sphere cloud or multiplied subgrid spray."""
import os,sys,json,gzip,time,gc
from pathlib import Path
for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS']:os.environ[name]='2'
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R.parent/'flip-lettering/vendor/tools'))
import numpy as np
from scipy.spatial import cKDTree
from bending_surface import DetailReconstruction,encode
O=R/'sigil-02-water-hold';source=O/'particles';out=O/'release-pilot-mesh';out.mkdir(exist_ok=True);pilot='--pilot' in sys.argv
preview='--preview' in sys.argv
if preview:out=O/'preview-mesh';out.mkdir(exist_ok=True)
frames=range(60,166,3) if preview else [200,225,260] if pilot else range(300);isolated=np.empty(0,bool);previous_ids=np.empty(0,np.uint32);previous_iso=1.8;begun=time.time()
guides=np.load(O/'guides.npz');guideTree=cKDTree(guides['points']);guideRadii=guides['radii']
for f in frames:
 if not pilot:
  while len(list(out.glob('*.mesh.gz')))>=5:time.sleep(.3)
 while True:
  try:m=json.loads((source/'manifest.json').read_text());info=m['frames'][f];break
  except (OSError,json.JSONDecodeError,IndexError):time.sleep(.5)
 blob=gzip.decompress((source/f'{f:04}.gz').read_bytes());n=info['particles'];h=m['config']['h'];extent=np.array(m['config']['extent'])
 if m.get('cacheFormat')=='position-u16-velocity-i16-id-u32':
  p=(np.frombuffer(blob,'<u2',n*3).reshape(-1,3)/65535*extent).astype(np.float32)
  v=(np.frombuffer(blob,'<i2',n*3,n*6).reshape(-1,3)/32767*m['cacheVelocityRange']).astype(np.float32)
  ids=np.frombuffer(blob,'<u4',n,n*12)
 else:
  raw=np.frombuffer(blob,'<f4');p=raw[:n*3].reshape(-1,3);v=raw[n*3:n*6].reshape(-1,3);ids=raw[n*6:].view('<u4')
 if len(previous_ids):
  prev=dict(zip(previous_ids.tolist(),isolated.tolist()));isolated=np.array([prev.get(int(i),False) for i in ids])
 else:isolated=np.zeros(n,bool)
 previous_ids=ids.copy();empty=np.empty((0,3),np.float32)
 if n>2048:
  origin=np.maximum(0,np.floor((p.min(0)-5*h)/h)*h);upper=np.minimum(extent,np.ceil((p.max(0)+5*h)/h)*h)
  cfg=dict(m['config']);cfg['extent']=(upper-origin).tolist();cfg['surfaceOptions']={'spacingFactor':.43,'kernelRadiusFactor':1.35,'fieldSigma':.42,'meshSmoothingPasses':4}
  rec=DetailReconstruction(cfg);rec.isolated=isolated;rec.previous_iso=previous_iso
  history=np.zeros((n,6),np.float32);history[:,:3]=1
  field,velocity,verts,normals,faces,drops,radii,dv,iso,measure=rec.reconstruct(p-origin,v,history,[],m['frameDt']);isolated=rec.isolated.copy();previous_iso=iso;verts+=origin
  tree=cKDTree(p);dist,nb=tree.query(verts,k=6,workers=2);weights=1/np.maximum(dist,h*.07)**2;weights/=weights.sum(1)[:,None];vv=np.einsum('nk,nkj->nj',weights,v[nb]).astype(np.float32)
  measure['unresolvedMarkerFraction']=float(isolated.mean());measure['renderedSubgridDrops']=0
  del field,velocity,history,tree,dist,nb,weights,rec,drops,radii,dv
 else:verts=normals=vv=empty;faces=np.empty((0,3),np.uint32);measure={'unresolvedMarkerFraction':1 if n else 0,'renderedSubgridDrops':0}
 if n:
  d,g=guideTree.query(p,workers=2);measure['fractionInsideTwiceGuideRadius']=float(np.mean(d<2*guideRadii[g]));measure['medianSpeed']=float(np.median(np.linalg.norm(v,axis=1)))
 assert np.isfinite(verts).all() and np.isfinite(vv).all()
 np.savez_compressed(out/f'{f:04}.velocity.npz',surface=vv,drops=empty,drop_positions=empty)
 (out/'manifest.json').write_text(json.dumps(m))
 row=dict(frame=f,vertices=len(verts),triangles=len(faces),renderedDrops=0,seconds=round(time.time()-begun,1),**measure);(out/f'{f:04}.json').write_text(json.dumps(row))
 encode(out/f'{f:04}.mesh.tmp',verts,normals,faces,empty,np.empty(0,np.float32),np.empty((0,6),np.float32),p[::max(1,n//10000)],extent,np.zeros(len(verts),np.float32),np.zeros((1,1,2),np.uint8));(out/f'{f:04}.mesh.tmp').replace(out/f'{f:04}.mesh.gz')
 if not pilot and not preview and f not in [45,75,120,165,200,240,299]:
  path=source/f'{f:04}.gz';assert path.resolve().parent==source.resolve();path.unlink()
 print('MESH',f,'vertices',len(verts),'unresolved',round(measure['unresolvedMarkerFraction'],3),'seconds',round(time.time()-begun,1),flush=True)
 del verts,normals,faces,vv,p,v;gc.collect()
print('MESH COMPLETE',flush=True)
