from pathlib import Path
import gzip,struct,numpy as np,json
root=Path(__file__).resolve().parent
rows=[]
for f in sorted((root/'cache-v2/mesh').glob('*.bobj.gz')):
 try:
  with gzip.open(f,'rb') as stream:
   n=struct.unpack('<i',stream.read(4))[0];p=np.frombuffer(stream.read(n*12),dtype='<f4').reshape(n,3)
  assert np.isfinite(p).all()
  rows.append({'frame':int(f.stem.split('_')[-1].split('.')[0]),'vertices':n,'bytes':f.stat().st_size})
 except EOFError:continue
(root/'mesh-check.json').write_text(json.dumps(rows))
print({'frames':len(rows),'nonempty':sum(r['vertices']>0 for r in rows),'maxVertices':max(r['vertices'] for r in rows)})
