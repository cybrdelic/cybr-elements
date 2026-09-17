import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parent
bpy.ops.mesh.primitive_cube_add();ob=bpy.context.object;mod=ob.modifiers.new('Native liquid domain','FLUID');mod.fluid_type='DOMAIN';d=mod.domain_settings;d.domain_type='LIQUID'
names=['resolution','cache','time','viscos','diffus','tension','particle','mesh','border','guid']
domain={p.identifier:{'type':p.type,'description':p.description,'enum':[i.identifier for i in p.enum_items] if p.type=='ENUM' else None} for p in d.bl_rna.properties if any(k in p.identifier for k in names)}
bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8);ob=bpy.context.object;mod=ob.modifiers.new('Liquid emitter','FLUID');mod.fluid_type='FLOW';f=mod.flow_settings;f.flow_type='LIQUID'
flow={p.identifier:{'type':p.type,'description':p.description,'enum':[i.identifier for i in p.enum_items] if p.type=='ENUM' else None} for p in f.bl_rna.properties}
(R/'native-fluid-properties.json').write_text(json.dumps({'domain':domain,'flow':flow},indent=2));print('Fluid API properties saved')
