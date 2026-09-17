"""A hard CPU process budget for simulations and spectral diagnostic renders."""
from pathlib import Path
import os,sys,time,json,subprocess,argparse,psutil
R=Path(__file__).resolve().parent;ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=int,default=100);ap.add_argument('script');ap.add_argument('args',nargs=argparse.REMAINDER);a=ap.parse_args();assert a.seconds<=180
script=(R/a.script).resolve();assert script.parent==R;env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2');key=script.stem+'-'+str(time.time_ns());out=R/'logs';out.mkdir(exist_ok=True);start=time.time();peak=0;status='running'
with (out/f'{key}.log').open('w') as log:
 p=subprocess.Popen([str(R/'.venv/Scripts/python.exe'),str(script),*a.args],cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));proc=psutil.Process(p.pid);proc.cpu_affinity(psutil.Process().cpu_affinity()[:2])
 while p.poll() is None:
  try:peak=max(peak,sum(q.memory_info().rss for q in [proc,*proc.children(recursive=True)] if q.is_running()))
  except psutil.Error:pass
  if time.time()-start>a.seconds or peak>3*1024**3:
   status='budget_stop'
   for child in proc.children(recursive=True):
    try:child.kill()
    except psutil.Error:pass
   p.kill();p.wait();break
  time.sleep(.25)
if status=='running':status='complete' if p.returncode==0 else 'failed'
report={'script':a.script,'args':a.args,'device':'CPU','status':status,'seconds':round(time.time()-start,3),'peakResidentMB':round(peak/1024**2,1),'returncode':p.returncode,'log':str(out/f'{key}.log')};(out/f'{key}.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));print((out/f'{key}.log').read_bytes()[-2200:].decode(errors='replace'))
sys.exit(0 if status=='complete' else 1)
