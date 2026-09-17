from pathlib import Path
R=Path(__file__).resolve().parent;s=(R/'sigil_02_water_hold_render.py').read_text()
s=s.replace('sigil-02-water-hold/pilot','sigil-02-water-hold/light-pilot').replace('[45,75,120,165]','[120,165]')
s=s.replace("else 1280","else 960").replace("else 720","else 540").replace("else 24","else 16")
s=s.replace("bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1)","""for light in bpy.data.lights:
 light.energy*=.035
 light.color=(.68,.86,1)
bg.inputs['Strength'].default_value=.12
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1)""")
(R/'sigil_02_water_hold_light_render.py').write_text(s)
print('Low-radiance light-only ablation prepared.')
