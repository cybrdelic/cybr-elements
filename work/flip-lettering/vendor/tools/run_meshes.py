from pathlib import Path
import subprocess,time,json,os
ROOT=Path(__file__).resolve().parents[1]
(ROOT/'logs').mkdir(parents=True,exist_ok=True)
for name in ['impact','breach','jets','cascade','slosh','vortex','paddle','capillary','viscous']:
 while True:
  path=ROOT/'cache'/name/'manifest.json'
  try:
   data=json.loads(path.read_text())
   if data['config'].get('transfer')=='apic-flip' and len(data['frames'])==120 and 'wallSeconds' in data:break
  except (FileNotFoundError,json.JSONDecodeError):pass
  time.sleep(3)
 env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
 with (ROOT/'logs'/f'mesh_{name}.log').open('w') as log:
  p=subprocess.run(['python','-u',str(ROOT/'tools/mesh_ii.py'),name],stdout=log,stderr=subprocess.STDOUT,env=env)
 if p.returncode:raise RuntimeError((ROOT/'logs'/f'mesh_{name}.log').read_text()[-4000:])
 print('DONE',name,flush=True)
