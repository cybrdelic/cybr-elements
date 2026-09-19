"""Reconstruct the saved lava continuum; do not overwrite or resimulate states."""
import argparse,time,json,shutil
from pathlib import Path
import numpy as np
from elements_core.lava_surface import reconstruct
from elements_core.runtime import RunIdentity,atomic_npz,atomic_json,digest

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--run',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
 p.add_argument('--frames',default=60,type=int);p.add_argument('--spacing',default=.006,type=float)
 p.add_argument('--frame',type=int);p.add_argument('--wait-timeout',default=7200,type=float)
 a=p.parse_args();settings=json.loads((a.run/'run.json').read_text());physics=settings['settings']['config'];floor=float(physics['floor']);contact_band=float(physics['spacing']);formation=settings['settings'].get('formation');formation_mode=settings['settings'].get('formationMode','formed')
 inputs={'physics':a.run/'run.json','entry':Path(__file__),'surface':Path(__file__).parent/'elements_core/lava_surface.py'}
 if (a.run/'mold.npz').is_file():inputs['mold']=a.run/'mold.npz'
 mold=None
 if (a.run/'mold.npz').is_file():
  with np.load(a.run/'mold.npz',allow_pickle=False) as md:
   required=['sdf','lo','extent','stageScale','sourceCenterZ','wallTop','margin']
   if all(k in md for k in required):
    mold={k:np.asarray(md[k]).copy() for k in md.files if k not in ('vertices','faces')}
 run=RunIdentity(a.out,dict(frames=a.frames,spacing=a.spacing,frame=a.frame,floor=floor,contactBand=contact_band,formation=formation,formationMode=formation_mode,moldConstrained=bool(mold is not None)),inputs)
 (a.out/'meshes').mkdir(exist_ok=True);rows=[];start=time.perf_counter()
 if (a.run/'mold.npz').is_file():
  shutil.copy2(a.run/'mold.npz',a.out/'mold.npz')
  run.receipt('mold-copy',[a.out/'mold.npz'],sourceSHA256=digest(a.run/'mold.npz'))
 for f in ([a.frame] if a.frame is not None else range(a.frames)):
  source=a.run/'particles'/f'{f:04d}.npz';deadline=time.monotonic()+a.wait_timeout
  while not source.exists():
   status=a.run/'status-simulation.json'
   if status.exists() and json.loads(status.read_text()).get('state')=='failed':raise RuntimeError('Producer failed')
   if time.monotonic()>deadline:raise TimeoutError(source)
   time.sleep(1)
  with np.load(source,allow_pickle=False) as s:mesh,row=reconstruct(dict(s),spacing=a.spacing,floor=floor,contact_band=contact_band,mold=mold)
  file=a.out/'meshes'/f'{f:04d}.npz';atomic_npz(file,**mesh,time=np.float64(row['frameTime']))
  row.update(frame=f,sourceSHA256=digest(source),wallSeconds=time.perf_counter()-start)
  atomic_json(a.out/'meshes'/f'{f:04d}.json',row);run.receipt(f'mesh-{f:04d}',[file],frame=f,sourceSHA256=digest(source))
  rows.append(row);atomic_json(a.out/'metrics.json',rows);print(json.dumps(row),flush=True)
 atomic_json(a.out/'manifest.json',dict(complete=True,frames=len(rows),spacing=a.spacing,floor=floor,contactBand=contact_band,formation=formation,formationMode=formation_mode,moldConstrained=bool(mold is not None),moldSHA256=digest(a.out/'mold.npz') if (a.out/'mold.npz').is_file() else None,elapsedSeconds=time.perf_counter()-start))
if __name__=='__main__':main()
