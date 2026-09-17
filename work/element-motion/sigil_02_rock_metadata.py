from pathlib import Path
import urllib.request,json
O=Path(__file__).resolve().parent/'sigil-02-repair/scans';O.mkdir(exist_ok=True)
for name in ['boulder_01','rock_07','rock_09']:
 req=urllib.request.Request(f'https://api.polyhaven.com/files/{name}',headers={'User-Agent':'Cybrdelic material study'})
 with urllib.request.urlopen(req,timeout=40) as r:data=json.load(r)
 (O/f'{name}-files.json').write_text(json.dumps(data,indent=2))
 print(name,'formats',list(data))
 for fmt in ['gltf','blend']:
  if fmt in data:print(fmt,json.dumps(data[fmt].get('2k',{}))[:3500])
