from pathlib import Path
import json,shutil,psutil
O=Path(__file__).resolve().parent/'sigil-02-repair'
release=(O/'release-jobs.json').exists()
for stem in (['release-sim','release-mesh','release-render','lightning-full'] if release else ['water-sim-full','water-mesh-full','water-render-full','earth-full','lightning-full']):
 p=O/f'{stem}.log'
 if p.exists():
  with p.open('rb') as h:h.seek(max(0,p.stat().st_size-90000));lines=h.read().decode(errors='replace').splitlines()
  useful=[q for q in lines if q.startswith(('FRAME ','MESH ','REPLAY ','COMPLETE','SIM COMPLETE','WATER ','EARTH ','ALL '))]
  print(stem, useful[-1] if useful else 'initializing')
 err=O/f'{stem}.err'
 if err.exists() and err.stat().st_size:print(stem,'ERROR',err.read_text(errors='replace')[-1000:])
print('frames',{e:len(list((O/f'{e}-frames').glob('*.jpg'))) for e in (['water-release','earth'] if release else ['water','earth'])})
if release:
 p=O/'water-release-particles/manifest.json'
 if p.exists():
  m=json.loads(p.read_text());f=m['frames'][-1];print('water simulation',len(m['frames']),'particles',f['particles'],'outflow',f['deleted'],'complete',m.get('complete',False))
print('diskGB',round(shutil.disk_usage(O).free/1024**3,2),'availableMemoryGB',round(psutil.virtual_memory().available/1024**3,2))
p=O/('release-jobs.json' if release else 'full-jobs.json')
if p.exists():print('running',{name:psutil.pid_exists(pid) for name,pid in json.loads(p.read_text()).items()})
