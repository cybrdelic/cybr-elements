"""Reconstruct new water particles in cropped high-resolution grids."""
import os,sys,json,gzip,time,gc
from pathlib import Path
for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS']:os.environ[name]='2'
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R.parent/'flip-lettering/vendor/tools'))
import numpy as np
from mesh_repair import DetailReconstruction,encode
B=R/'bending-rebuild-v2';source=B/'water-particles';out=B/'water-mesh-smooth';out.mkdir(parents=True,exist_ok=True)
frames=range(120) if '--full' in sys.argv else [21,42,45]
started=time.time();stats=[]
for f in frames:
 if (out/f'{f:04}.mesh.gz').exists():continue
 while True:
  try:
   m=json.loads((source/'manifest.json').read_text());info=m['frames'][f];break
  except (OSError,json.JSONDecodeError,IndexError):time.sleep(.4)
 n=info['particles'];raw=np.frombuffer(gzip.decompress((source/f'{f:04}.gz').read_bytes()),'<f4')
 p=raw[:n*3].reshape(-1,3);v=raw[n*3:].reshape(-1,3);extent=np.array(m['config']['extent']);h=m['config']['h']
 if n>4:
  origin=np.maximum(0,np.floor((p.min(0)-5*h)/h)*h);upper=np.minimum(extent,np.ceil((p.max(0)+5*h)/h)*h)
  config=dict(m['config']);config['extent']=(upper-origin).tolist();config['surfaceOptions']={'spacingFactor':.36,'kernelRadiusFactor':1.08,'fieldSigma':.46,'meshSmoothingPasses':4}
  rec=DetailReconstruction(config);history=np.zeros((n,6),np.float32);history[:,:3]=1
  field,velocity,verts,normals,faces,drops,radii,dv,iso,measure=rec.reconstruct(p-origin,v,history,[],m['frameDt'])
  verts+=origin;drops+=origin
  del field,velocity,rec,history
 else:
  verts=normals=drops=np.empty((0,3),np.float32);faces=np.empty((0,3),np.uint32);radii=np.empty(0,np.float32);measure={}
 assert np.isfinite(verts).all()
 encode(out/f'{f:04}.mesh.gz',verts,normals,faces,drops,radii,np.empty((0,6),np.float32),p[::max(1,n//10000)],extent,np.zeros(len(verts),np.float32),np.zeros((1,1,2),np.uint8))
 (out/'manifest.json').write_text(json.dumps(m))
 row={'frame':f,'vertices':len(verts),'triangles':len(faces),'drops':len(drops),'seconds':round(time.time()-started,1),**measure}
 (out/f'{f:04}.json').write_text(json.dumps(row));stats.append(row)
 print('MESH',f,'verts',len(verts),'drops',len(drops),'seconds',round(time.time()-started,1),flush=True)
 del verts,normals,faces,drops,p,v;gc.collect()
print('MESH COMPLETE',flush=True)
