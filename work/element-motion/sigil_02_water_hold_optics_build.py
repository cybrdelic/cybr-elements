from pathlib import Path
r=Path(__file__).resolve().parent
s=(r/'sigil_02_water_hold_render.py').read_text()
s=s.replace("out=R/('sigil-02-water-hold/frames' if '--full' in sys.argv else 'sigil-02-water-hold/pilot')", "out=R/'sigil-02-water-hold/optics-pilot'")
s=s.replace("frames=range(300) if '--full' in args else [45,75,120,165]", "frames=[75,165]")
s=s.replace("for light in bpy.data.lights:light.energy*=.44", """for light in bpy.data.lights:
 light.energy*=.11
 light.color=(.64,.83,1.0)
for light_object in bpy.data.objects:
 if light_object.type=='LIGHT':light_object.visible_transmission=False
bg.inputs['Strength'].default_value=.48
for e in cr.elements:
 c=e.color[:];e.color=(c[0]*.68,c[1]*.86,c[2],1)
""")
(r/'sigil_02_water_hold_optics_render.py').write_text(s)
print('Optics comparison: reflected soft blue studio, black transmitted backdrop')
