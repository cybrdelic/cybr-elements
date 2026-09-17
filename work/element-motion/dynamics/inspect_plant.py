import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parent
with bpy.data.libraries.load(str(R.parent/'realism/assets/nettle_plant_2k.blend'),link=False) as (a,b):b.materials=a.materials
def describe(tree):
    return [{'type':n.type,'name':n.name,'inputs':list(n.inputs.keys()),'children':describe(n.node_tree) if n.type=='GROUP' else []} for n in tree.nodes]
(R/'plant-material-nodes.json').write_text(json.dumps({m.name:describe(m.node_tree) for m in b.materials if m.use_nodes},indent=2),encoding='utf-8')
print('Inspected',len(b.materials),'materials')
