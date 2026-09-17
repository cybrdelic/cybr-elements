import sys,os,time,json
from pathlib import Path
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS']:os.environ[k]='2'
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'flip-lettering/vendor/tools'))
import numpy as np
from mesh_repair import DetailReconstruction,DiffuseWhitewater
from pareto import ParetoBreakup
breakup=ParetoBreakup()
m=json.loads((ROOT/'cache/manifest.json').read_text());rec=DetailReconstruction(m['config']);ww=DiffuseWhitewater(8608);out=ROOT/'meshes';out.mkdir(exist_ok=True);stats=[];start=time.time()
frames=[int(sys.argv[1])] if len(sys.argv)>1 else range(192)
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
 drops,radii,breakup_error=breakup.apply(drops,radii,dv,m['frameDt'])
 # Transform new secondary radii once, using their original log-uniform quantiles.
 born=ww.age==0
 if np.any(born):
  u=np.clip(np.log(ww.radius[born]/(rec.h*.030))/np.log(.14/.030),0,1);ww.radius[born]=rec.h*.018*(1-u*(1-(.18/.018)**-1.7))**(-1/1.7);white[:,3]=ww.radius
 assert np.isfinite(verts).all() and np.isfinite(radii).all()
 np.savez_compressed(out/f'{f:04}.npz',verts=verts,normals=normals,faces=faces,drops=drops,radii=radii,white=white)
 stats.append({'breakupVolumeError':breakup_error,'radiusP50':float(np.quantile(radii,.5)) if len(radii) else 0,'radiusP95':float(np.quantile(radii,.95)) if len(radii) else 0,'frame':f,'vertices':len(verts),'droplets':len(drops),'dropRadiusMax':float(radii.max()) if len(radii) else 0,'whitewater':len(white),**measure});(ROOT/'mesh-report.json').write_text(json.dumps(stats))
 print('MESH',f,len(verts),len(drops),len(white),round(time.time()-start,1),flush=True)
