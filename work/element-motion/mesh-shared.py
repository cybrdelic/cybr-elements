import sys,os,json,gzip,time
from pathlib import Path
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS']:os.environ[k]='2'
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R.parent/'flip-lettering/vendor/tools'))
import numpy as np
from mesh_repair import DetailReconstruction,encode
variant=sys.argv[1];folder=R/'water-shared-cache';m=json.loads((folder/'manifest.json').read_text())
out=R.parent.parent/f'outputs/cybrdelic-type/elements/motion/water/cache/{variant}';out.mkdir(parents=True,exist_ok=True)
all_frames=len(sys.argv)>2 and sys.argv[2]=='all'
frames=range(120) if all_frames else [int(x) for x in sys.argv[2].split(',')] if len(sys.argv)>2 else range(len(m['frames']));stats=[];start=time.time()
if all_frames and (R/f'mesh-{variant}.json').exists():
 try:stats=json.loads((R/f'mesh-{variant}.json').read_text())
 except json.JSONDecodeError:stats=[]
done={x['frame'] for x in stats if (out/f"{x['frame']:04}.mesh.gz").exists()}
for f in frames:
 if f in done:continue
 while True:
  try:
   current=json.loads((folder/'manifest.json').read_text())
   if len(current['frames'])>f:m=current;break
  except (OSError,json.JSONDecodeError):pass
  time.sleep(.5)
 info=m['frames'][f];n=info['particles'];raw=np.frombuffer(gzip.decompress((folder/f'{f:04}.gz').read_bytes()),'<f4');p=raw[:n*3].reshape(-1,3);v=raw[n*3:].reshape(-1,3)
 history=np.zeros((n,6),np.float32);history[:,:3]=1
 extent=np.array(m['config']['extent']);h=m['config']['h']
 if n:
  # Crop empty space only; retain reference voxel spacing and eight-cell padding.
  origin=np.maximum(0,np.floor((p.min(0)-8*h)/h)*h);upper=np.minimum(extent,np.ceil((p.max(0)+8*h)/h)*h)
  config=dict(m['config']);config['extent']=(upper-origin).tolist();rec=DetailReconstruction(config)
  field,vel,verts,normals,faces,drops,radii,dv,iso,measure=rec.reconstruct(p-origin,v,history,[],info.get('dt',m['frameDt']));verts+=origin;drops+=origin
 else:
  verts=normals=drops=np.empty((0,3),np.float32);faces=np.empty((0,3),np.uint32);radii=np.empty(0,np.float32);measure={}
 assert np.isfinite(verts).all() and np.isfinite(normals).all()
 # Use reconstructed isolated primary droplets only. No decorative spray copies.
 white=np.empty((0,6),np.float32);foam=np.zeros(len(verts),np.float32);caustic=np.zeros((1,1,2),np.uint8)
 digest=encode(out/f'{f:04}.mesh.gz',verts,normals,faces,drops,radii,white,p[::max(1,n//18000)],extent,foam,caustic)
 stats.append({'frame':f,'vertices':len(verts),'triangles':len(faces),'drops':len(drops),'sha256':digest,**measure})
 (out/'manifest.json').write_text(json.dumps(m))
 (out/'progress.json').write_text(json.dumps({'lastFrame':f}))
 (R/f'mesh-{variant}.json').write_text(json.dumps(stats));print('MESH',variant,f,len(verts),len(drops),round(time.time()-start,1),flush=True)
(out/'manifest.json').write_text(json.dumps(m));print('COMPLETE',flush=True)
