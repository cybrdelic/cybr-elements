"""Sequential CPU optical renders with complete fresh-frame receipts."""
from pathlib import Path
import json,sys,subprocess,time,hashlib,os,psutil
R=Path(__file__).resolve().parent;(R/'receipts').mkdir(exist_ok=True)
if (R/'cpu-only-hold.json').exists():raise SystemExit('Full movie queue blocked: use bounded CPU stills first.')
jobs=json.loads(Path(sys.argv[1]).read_text())
for job in jobs:
 kind=job['kind'];script=R/job['script']
 while psutil.virtual_memory().available<.85e9:time.sleep(10)
 start=time.time();source_hash=hashlib.sha256(script.read_bytes()).hexdigest();env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
 print('START CPU',kind,flush=True)
 with (R/f'cpu-{kind}.log').open('w') as log:code=subprocess.run([sys.executable,str(script),'--kind',kind,'--full'],stdout=log,stderr=subprocess.STDOUT,env=env).returncode
 if code:raise SystemExit(f'{kind} failed: see its log')
 digest=hashlib.sha256()
 for f in range(120):
  p=R/'frames'/kind/f'{f:04}.jpg';assert p.exists() and p.stat().st_mtime>=start-1;digest.update(p.read_bytes())
 assert hashlib.sha256(script.read_bytes()).hexdigest()==source_hash
 (R/'receipts'/f'{kind}.json').write_text(json.dumps({'id':kind,'fresh':True,'frames':list(range(120)),'frameDigest':digest.hexdigest(),'sources':{script.name:source_hash},'seconds':time.time()-start},indent=2))
 subprocess.run([sys.executable,str(R/'encode.py'),kind],check=True)
 print('COMPLETE CPU',kind,round(time.time()-start,1),'seconds',flush=True)
