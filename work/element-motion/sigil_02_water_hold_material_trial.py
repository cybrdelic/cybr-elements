from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'sigil_02_water_hold_render.py').read_text()
s=s.replace('sigil-02-water-hold/pilot','sigil-02-water-hold/material-pilot').replace('[45,75,120,165]','[75,165]')
needle="bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1)"
block="""# A small amount of volume scattering represents fine entrained air. The
# surface remains fully transmissive water; no diffuse paint or image overlay.
scatter=m.node_tree.nodes.new('ShaderNodeVolumeScatter');scatter.inputs['Color'].default_value=(.72,.89,1,1);scatter.inputs['Density'].default_value=.16;scatter.inputs['Anisotropy'].default_value=.20
addVolume=m.node_tree.nodes.new('ShaderNodeAddShader');m.node_tree.links.new(absorb.outputs[0],addVolume.inputs[0]);m.node_tree.links.new(scatter.outputs[0],addVolume.inputs[1]);m.node_tree.links.new(addVolume.outputs[0],m.node_tree.nodes.get('Material Output').inputs['Volume'])
for light in bpy.data.lights:
 if light.name=='Edge card':light.energy*=.32
 elif light.name=='Long white strip':light.energy*=.65
 elif light.name=='Soft rim':light.energy*=.70
"""
s=s.replace(needle,block+needle)
(R/'sigil_02_water_hold_material_render.py').write_text(s)
print('Material-only CPU comparison prepared from identical cached fluid states.')
