from pathlib import Path
import urllib.request,urllib.parse,json,hashlib
O=Path(__file__).resolve().parent/'sigil-02-repair/scans'
report=[]
for name,author in [('boulder_01','Rico Cilliers'),('rock_07','Jenelle van Heerden'),('rock_09','Jenelle van Heerden')]:
 meta=json.loads((O/f'{name}-files.json').read_text());bundle=meta['gltf']['2k']['gltf'];folder=O/name;folder.mkdir(exist_ok=True)
 files={f'{name}_2k.gltf':bundle,**bundle['include']}
 for rel,info in files.items():
  path=(folder/rel).resolve();assert path.is_relative_to(folder.resolve());assert urllib.parse.urlparse(info['url']).hostname=='dl.polyhaven.org';assert info['size']<12_000_000
  path.parent.mkdir(parents=True,exist_ok=True)
  if not path.exists():
   req=urllib.request.Request(info['url'],headers={'User-Agent':'Cybrdelic material study'})
   with urllib.request.urlopen(req,timeout=60) as r:path.write_bytes(r.read())
  assert hashlib.md5(path.read_bytes()).hexdigest()==info['md5'],rel
 report.append(dict(asset=name,author=author,license='CC0',source=f'https://polyhaven.com/a/{name}',files=len(files),bytes=sum(v['size'] for v in files.values())))
 print(name,'verified',len(files),'files',sum(v['size'] for v in files.values()),'bytes')
(O/'attribution.json').write_text(json.dumps(report,indent=2))
