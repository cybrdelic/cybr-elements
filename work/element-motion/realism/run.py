import sys,subprocess,json,time
from pathlib import Path
R=Path(__file__).resolve().parent
BLENDER='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
jobs=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'));state=[]
for job in jobs:
 name=job['name'];log=R/(name+'.log');started=time.time()
 with log.open('w',encoding='utf-8') as stream:
  result=subprocess.run([BLENDER,'-b','--factory-startup','--python',str(R/job['script']),'--',*job.get('args',[])],stdout=stream,stderr=subprocess.STDOUT)
 tail=log.read_bytes()[-2500:].decode('utf-8',errors='replace')
 failed=result.returncode!=0 or 'Traceback' in tail or 'Error: Python' in tail
 state.append({'name':name,'seconds':round(time.time()-started,1),'ok':not failed,'log':str(log)})
 (R/(Path(sys.argv[1]).stem+'-status.json')).write_text(json.dumps(state,indent=2),encoding='utf-8')
 print(name, 'FAILED' if failed else 'DONE',state[-1]['seconds'],flush=True)
 if failed:print(tail[-700:].encode('ascii','replace').decode(),flush=True);sys.exit(1)
