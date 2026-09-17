import bpy
m=bpy.data.materials.new('probe')
print('MATERIAL_CYCLES',[(p.identifier,p.type) for p in m.cycles.bl_rna.properties])
