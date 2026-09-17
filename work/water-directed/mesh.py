import sys,os,time,json
from pathlib import Path
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS']:os.environ[k]='2'
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'flip-lettering/vendor/tools'))
import numpy as np
from mesh_repair import DetailReconstruction,DiffuseWhitewater
from spray import SelectiveSpray
m=json.loads((ROOT/'cache-directed/manifest.json').read_text());m['config']['surfaceOptions'].update({'fieldSigma':.6,'kernelRadiusFactor':1.08,'meshSmoothingPasses':4});rec=DetailReconstruction(m['config']);ww=SelectiveSpray(8608);out=ROOT/'meshes-final';out.mkdir(exist_ok=True);stats=[];start=time.time()
frames=[int(x) for x in sys.argv[1].split(',')] if len(sys.argv)>1 else range(240)
for f in frames:
 while True:
  try:
   m=json.loads((ROOT/'cache-directed/manifest.json').read_text())
   if len(m['frames'])>f:break
  except json.JSONDecodeError:pass
  time.sleep(1)
 n=m['frames'][f]['particles'];raw=np.fromfile(ROOT/f'cache-directed/{f:04}.particles','<f4');p=raw[:n*3].reshape(-1,3);v=raw[n*3:].reshape(-1,3);history=np.fromfile(ROOT/f'cache-directed/{f:04}.shape','<f4').reshape(n,6)
 field,vel,verts,normals,faces,drops,radii,dv,iso,measure=rec.reconstruct(p,v,history,[],m['frameDt'])
 white=ww.step(p,v,field,vel,rec.spacing,rec.h,m['frameDt'],iso,rec.extent,[],True) if len(sys.argv)==1 else np.empty((0,6),np.float32)
 assert np.isfinite(verts).all() and np.isfinite(radii).all()
 temp=out/f'{f:04}.tmp.npz';np.savez_compressed(temp,verts=verts,normals=normals,faces=faces,drops=drops,radii=radii,white=white);os.replace(temp,out/f'{f:04}.npz')
 stats.append({'frame':f,'vertices':len(verts),'droplets':len(drops),'dropRadiusMax':float(radii.max()) if len(radii) else 0,'whitewater':len(white),**measure});(ROOT/'mesh-report.json').write_text(json.dumps(stats))
 print('MESH',f,len(verts),len(drops),len(white),round(time.time()-start,1),flush=True)
