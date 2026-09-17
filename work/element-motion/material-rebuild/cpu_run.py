"""Serial, resource-bounded CPU stills. Never starts the movie queues."""
from pathlib import Path
import os,sys,json,hashlib,time,subprocess,argparse,psutil
R=Path(__file__).resolve().parent
from cpu_catalog import catalog
ap=argparse.ArgumentParser();ap.add_argument('--kinds',required=True);ap.add_argument('--frames');ap.add_argument('--samples',type=int,default=24);args=ap.parse_args()
assert (R/'cpu-only-hold.json').exists()
assert 8<=args.samples<=48
audit=json.loads((R/'cpu/audit.json').read_text());checks={x['id']:x for x in audit['materials']}
recipes={x['id']:x for x in catalog()};root=R/'cpu/proofs';root.mkdir(parents=True,exist_ok=True)
def source_signature(recipe):
 # Restrict the signature to actual shared/recipe sources, so an unrelated
 # material edit does not invalidate every CPU image.
 names=['cpu_run.py','cpu_stage.py','cpu_bootstrap.py','cpu_geometry.py','common.py',recipe['script']]
 files=[R/n for n in names]+[R.parent/'dynamics/scene.py',R.parent/'dynamics/cache_io.py',R.parent/'shared_motion.py',R.parent/'shared-trail.json']
 if recipe['id'] in ['glass','plants']:files.append(R.parent/'dynamics'/('render_glass.py' if recipe['id']=='glass' else 'render_botanical.py'))
 if recipe['id']=='crystal':files.append(R.parent/'realism/solids.py')
 if recipe['id']=='seismic':files.append(R.parent/'dynamics/seismic.py')
 if recipe['id'] in ['ice','glass']:files.append(R/'optical_lighting.py')
 h=hashlib.sha256()
 for p in sorted(set(files)):h.update(p.name.encode());h.update(p.read_bytes())
 return h.hexdigest()
for kind in args.kinds.split(','):
 recipe=recipes[kind];assert not checks[kind]['hardErrors'],checks[kind]['hardErrors']
 revision=source_signature(recipe)
 assert (R/recipe['script']).exists(),recipe['script']
 frames=list(map(int,args.frames.split(','))) if args.frames else [recipe['frame']]
 for frame in frames:
  assert 0<=frame<120
  hh=hashlib.sha256((revision+kind+str(frame)+str(args.samples)).encode())
  inputs=list((R/'data'/kind).glob(f'{frame:04}.npz'))+list((R.parent/'dynamics/cache'/kind).glob('*.npz'))+list((R.parent/'dynamics/cache'/kind).glob(f'{frame:04}.npz'))
  inputs+=list((R/'cpu/identity').glob(f'{kind}-{frame:04}.npz'))+list((R/'cpu/witness').glob(f'{kind}.npz'))
  for p in sorted(set(inputs)):
   hh.update(str(p).encode());hh.update(str(p.stat().st_size).encode());hh.update(str(p.stat().st_mtime_ns).encode())
  key=hh.hexdigest()[:16];dest=root/kind/key;dest.mkdir(parents=True,exist_ok=True);receipt=dest/'run.json'
  if receipt.exists() and json.loads(receipt.read_text()).get('status')=='complete':
   print('REUSE',kind,frame,str(dest),flush=True);continue
  env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='-1',HIP_VISIBLE_DEVICES='-1',ROCR_VISIBLE_DEVICES='-1',CYBR_CPU_PROOF='1',CYBR_CPU_OUTPUT=str(dest),CYBR_CPU_SAMPLES=str(args.samples),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
  if kind in ['spirit-projection','lightning-redirection']:env.update(CYBR_CPU_VIEW_WIDTH='10.5',CYBR_CPU_VIEW_CENTER_X='0')
  if recipe['engine']=='numpy':cmd=[sys.executable,str(R/recipe['script']),'--kind',kind,'--frames',str(frame)]
  else:cmd=['C:/Program Files/Blender Foundation/Blender 4.5/blender.exe','--factory-startup','-b','-t','2','--python-exit-code','1','--python',str(R/'cpu_bootstrap.py'),'--','--script',str(R/recipe['script']),'--kind',kind,'--frames',str(frame)]
  started=time.time();peak=0;status='running'
  with (dest/'render.log').open('w') as log:
   p=subprocess.Popen(cmd,cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));monitor=psutil.Process(p.pid)
   allowed=psutil.Process().cpu_affinity();monitor.cpu_affinity(allowed[:2])
   while p.poll() is None:
    try:
     rss=monitor.memory_info().rss+sum(ch.memory_info().rss for ch in monitor.children(recursive=True) if ch.is_running());peak=max(peak,rss)
    except psutil.Error:rss=0
    elapsed=time.time()-started
    if elapsed>100 or rss>3*1024**3:
     status='time_limit' if elapsed>100 else 'memory_limit'
     for ch in monitor.children(recursive=True):
      try:ch.kill()
      except psutil.Error:pass
     p.kill();p.wait();break
    time.sleep(.25)
  images=sorted(dest.glob('*.png'));metadata=sorted(q for q in dest.glob('*.json') if q.name!='run.json')
  if status=='running':status='complete' if p.returncode==0 and images and metadata else 'failed'
  result={'kind':kind,'frame':frame,'status':status,'seconds':round(time.time()-started,3),'peakResidentMB':round(peak/1024**2,1),'device':'CPU','threads':2,'processorAffinity':allowed[:2],'samples':args.samples if recipe['engine']=='blender' else None,'sourceHash':revision,'returncode':p.returncode,'images':[q.name for q in images],'key':key}
  receipt.write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
  if status!='complete':print((dest/'render.log').read_bytes()[-2600:].decode(errors='replace'),flush=True)
