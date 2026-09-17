"""One GPU render at a time, with fresh-frame receipts and bounded log output."""
from pathlib import Path
import json,sys,subprocess,time,hashlib,psutil
R=Path(__file__).resolve().parent;B='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe';jobs=json.loads(Path(sys.argv[1]).read_text());receipts=R/'receipts';receipts.mkdir(exist_ok=True)
if (R/'cpu-only-hold.json').exists():raise SystemExit('Full render queue blocked: user requested CPU validation and CPU stills first.')
for job in jobs:
 kind=job['kind'];script=R/job['script'];frames=job.get('frames','full');requested=list(range(120)) if frames=='full' else [int(f) for f in frames.split(',')]
 while psutil.virtual_memory().available<job.get('minimumFreeGB',1.35)*1e9:time.sleep(10)
 start=time.time();hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [script,R/'common.py']}
 cmd=[B,'--factory-startup','-b','-t','3','--python-exit-code','1','--python',str(script),'--','--kind',kind]+(['--full'] if frames=='full' else ['--frames',frames])
 print('START',kind,frames,flush=True)
 with (R/f"job-{kind}-{frames.replace(',','-')}.log").open('w') as log:p=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
 if p.returncode:raise SystemExit(f'{kind} failed with exit {p.returncode}; see its on-disk log')
 digest=hashlib.sha256()
 for f in requested:
  file=R/'frames'/kind/f'{f:04}.jpg';assert file.exists() and file.stat().st_mtime>=start-1,(kind,f,'missing fresh frame');digest.update(file.read_bytes())
 assert all(hashlib.sha256((R/n).read_bytes()).hexdigest()==h for n,h in hashes.items()),'Renderer changed during the job'
 if frames=='full':
  (receipts/f'{kind}.json').write_text(json.dumps({'id':kind,'fresh':True,'frames':requested,'frameDigest':digest.hexdigest(),'sources':hashes,'seconds':time.time()-start},indent=2))
  subprocess.run([sys.executable,str(R/'encode.py'),kind],check=True)
 print('COMPLETE',kind,len(requested),'frames',round(time.time()-start,1),'seconds',flush=True)
