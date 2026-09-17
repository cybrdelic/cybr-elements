from pathlib import Path
import subprocess,time,sys,json
R=Path(__file__).resolve().parent
while not (R/'combustion-report.json').exists():time.sleep(3)
# The CUDA process must finish and release its allocation before Cycles starts.
time.sleep(3)
pilot=[{'name':'ice-pbr-black-pilot','script':'fracture.py','args':['--kind','ice','--frame','42']}]
(R/'ice-pbr-pilot.json').write_text(json.dumps(pilot),encoding='utf-8')
subprocess.run([sys.executable,str(R/'run.py'),str(R/'ice-pbr-pilot.json')],check=True)
print('Ice PBR pilot is ready for review.',flush=True)
workers=[]
for name in ['production-a','production-b','production-c']:
 log=(R/(name+'.log')).open('w',encoding='utf-8');proc=subprocess.Popen([sys.executable,str(R/'run.py'),str(R/(name+'.json'))],stdout=log,stderr=subprocess.STDOUT);workers.append((name,proc,log));print(name,'PID',proc.pid,flush=True)
for name,proc,log in workers:
 code=proc.wait();log.close();print(name,'exit',code,flush=True)
 if code:sys.exit(code)
