from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess,json,time
ROOT=Path(__file__).resolve().parents[1]
(ROOT/'logs').mkdir(parents=True,exist_ok=True)
def job(item):
 name,quality=item
 with (ROOT/'logs'/f'sim_{name}.log').open('w') as log:
  p=subprocess.run(['node',str(ROOT/'tools/simulate.mjs'),name,'120',quality],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
 if p.returncode:raise RuntimeError(f'{name} failed: '+(ROOT/'logs'/f'sim_{name}.log').read_text()[-3000:])
 return name
if __name__=='__main__':
 jobs=[('impact','ultra'),('breach','ultra'),('jets','ultra'),('cascade','high'),('slosh','high'),('vortex','high'),('paddle','high'),('capillary','high'),('viscous','high')]
 with ThreadPoolExecutor(max_workers=2) as pool:
  for result in pool.map(job,jobs):print('DONE',result,flush=True)
