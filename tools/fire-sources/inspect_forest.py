from pathlib import Path
import bpy,json
root=Path(__file__).resolve().parents[3]
path=root/'world/output/forest-surface/forest.blend'
with bpy.data.libraries.load(str(path),link=False) as (src,dst):
    names=[n for n in src.objects if n.startswith('Variant ') or n=='Neighbour-aware forest crowns']
    print(json.dumps({'objects':names[-10:],'count':len(names)}),flush=True)
    dst.objects=[next(n for n in names if n.startswith('Variant 1 wood')),next(n for n in names if n.startswith('Variant 1 roots'))]
for o in bpy.data.objects:
    if o.type=='MESH':print(json.dumps({'name':o.name,'vertices':len(o.data.vertices),'polygons':len(o.data.polygons),'location':list(o.location),'first':list(o.data.vertices[0].co),'dimensions':list(o.dimensions)}),flush=True)
