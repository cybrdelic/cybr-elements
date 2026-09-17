import bpy,json
from pathlib import Path
r=Path(__file__).resolve().parent
with bpy.data.libraries.load(str(r/'assets/nettle_plant_2k.blend'),link=False) as (a,b):b.objects=a.objects
rows=[]
for o in b.objects:
 if o.type=='MESH':rows.append({'name':o.name,'verts':len(o.data.vertices),'faces':len(o.data.polygons),'materials':[m.name for m in o.data.materials],'bbox':[list(v) for v in o.bound_box]})
(r/'asset-audit.json').write_text(json.dumps(rows,indent=2));print([(x['name'],x['verts']) for x in rows])
