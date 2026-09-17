from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess,sys,time,json
r=Path(__file__).resolve().parents[1]
(r/'logs').mkdir(parents=True,exist_ok=True)
def record(scene):
 if (r/'tests'/'captures'/f'{scene}.json').exists() and all((r/'media'/'shots'/f'{scene}_{shot}_1080p.mp4').exists() for shot in ['wide','surface']):
  return scene+' already rendered' 
 while True:
  try:
   m=json.loads((r/'cache'/scene/'manifest.json').read_text())
   if len(m.get('meshes',[]))==120 and 'meshVolumeRelativeError' in m['meshes'][0]:break
  except (OSError,ValueError,KeyError):pass
  time.sleep(3)
 for attempt in range(3):
  with open(r/'logs'/f'record_{scene}.log','w') as f:
   p=subprocess.run([sys.executable,str(r/'tools'/'record.py'),scene],stdout=f,stderr=subprocess.STDOUT)
  if p.returncode==0:break
  print('RETRY',scene,attempt+1,flush=True);time.sleep(3)
 if p.returncode:raise RuntimeError(f'Record failed: {scene}; see logs.')
 return scene
with ThreadPoolExecutor(max_workers=2) as pool:
 for scene in pool.map(record,['breach','impact','jets','cascade','slosh','vortex','paddle','capillary','viscous']):print('RECORDED',scene,flush=True)
