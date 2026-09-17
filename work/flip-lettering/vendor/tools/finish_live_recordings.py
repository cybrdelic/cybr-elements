from browser_common import ROOT
import subprocess
(ROOT/'logs').mkdir(parents=True,exist_ok=True)
for args,log in [(['tools/record_gpu.py'],'gpu-recording.log'),(['tools/record.py','--live'],'live-worker.log')]:
 with open(ROOT/'logs'/log,'w') as f:subprocess.run(['python',*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
