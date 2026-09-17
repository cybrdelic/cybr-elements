import sys,os,time,json
from pathlib import Path
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS']:os.environ[k]='2'
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor/tools'))
import numpy as np
from mesh_repair import DetailReconstruction,DiffuseWhitewater
m=json.loads((ROOT/'cache/manifest.json').read_text());rec=DetailReconstruction(m['config']);ww=DiffuseWhitewater(8608);out=ROOT/'meshes';out.mkdir(exist_ok=True);stats=[];start=time.time()
frames=[int(sys.argv[1])] if len(sys.argv)>1 else range(96)
for f in frames:
 while True:
  try:
   m=json.loads((ROOT/'cache/manifest.json').read_text())
   if len(m['frames'])>f:break
  except json.JSONDecodeError:pass
  time.sleep(1)
 n=m['frames'][f]['particles'];raw=np.fromfile(ROOT/f'cache/{f:04}.particles','<f4');p=raw[:n*3].reshape(-1,3);v=raw[n*3:].reshape(-1,3);history=np.fromfile(ROOT/f'cache/{f:04}.shape','<f4').reshape(n,6)
 field,vel,verts,normals,faces,drops,radii,dv,iso,measure=rec.reconstruct(p,v,history,[],m['frameDt'])
 white=ww.step(p,v,field,vel,rec.spacing,rec.h,m['frameDt'],iso,rec.extent,[],True)
 assert np.isfinite(verts).all() and np.isfinite(radii).all()
 np.savez_compressed(out/f'{f:04}.npz',verts=verts,normals=normals,faces=faces,drops=drops,radii=radii,white=white)
 stats.append({'frame':f,'vertices':len(verts),'droplets':len(drops),'dropRadiusMax':float(radii.max()) if len(radii) else 0,'whitewater':len(white),**measure});(ROOT/'mesh-report.json').write_text(json.dumps(stats))
 print('MESH',f,len(verts),len(drops),len(white),round(time.time()-start,1),flush=True)
