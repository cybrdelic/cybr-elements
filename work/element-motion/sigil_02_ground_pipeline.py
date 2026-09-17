"""Reuse the reviewed water optics/reconstruction; add floor and shot framing."""
from pathlib import Path
R=Path(__file__).resolve().parent
mesh=(R/'sigil_02_water_arrival_full_mesh.py').read_text()
mesh=mesh.replace("O=R/'sigil-02-water-arrival/full'", "O=R/'sigil-02-bending-ground'/('full' if '--full' in sys.argv else 'cpu')")
mesh=mesh.replace("frames=range(9,121,3) if preview else [12,24,36,48,60,75,90,120] if pilot else range(300)", "frames=list(range(0,390,6))+[389] if preview else [0,18,42,66,90,114,144,180,234,270,300,354,389] if pilot else range(390)")
mesh=mesh.replace("f not in [24,48,75,90,120,165,200,240,299]", "f not in [0,66,114,180,234,270,300,354,389]")
(R/'sigil_02_ground_mesh.py').write_text(mesh)
render=(R/'sigil_02_water_arrival_full_render.py').read_text()
start=render.index("R=Path(__file__)");end=render.index("while not (cache/",start)
render=render[:start]+"R=Path(__file__).resolve().parent;full='--full' in sys.argv;O=R/'sigil-02-bending-ground'/('full' if full else 'cpu');cache=O/('preview-mesh' if '--preview' in sys.argv else 'mesh');out=O/('frames' if full else 'preview-frames' if '--preview' in sys.argv else 'pilot');out.mkdir(exist_ok=True)\n"+render[end:]
render=render.replace("location=(.65,-16.8,4.2375)","location=(.25,-17.2,5.1)").replace("Vector((0,0,2.8875))","Vector((0,0,1.55))").replace("cam.data.lens=44","cam.data.lens=48")
floor="""
# A real opaque stage floor matches the native solid collider exactly.
bpy.ops.mesh.primitive_plane_add(size=40,location=(0,0,0));floor=bpy.context.object;floor.name='Ground / matches FLIP collider'
fm=bpy.data.materials.new('Black ground / contact');fm.use_nodes=True;fp=fm.node_tree.nodes.get('Principled BSDF');fp.inputs['Base Color'].default_value=(.012,.012,.012,1);fp.inputs['Roughness'].default_value=.65;fp.inputs['Specular IOR Level'].default_value=.012;floor.data.materials.append(fm)
# Studio environment illuminates transmissive water, but not the matte stage.
camera_or_diffuse=wn.new('ShaderNodeMath');camera_or_diffuse.operation='MAXIMUM';wl.new(lp.outputs['Is Camera Ray'],camera_or_diffuse.inputs[0]);wl.new(lp.outputs['Is Diffuse Ray'],camera_or_diffuse.inputs[1]);wl.new(camera_or_diffuse.outputs[0],mix.inputs[0])
"""
render=render.replace("bpy.ops.mesh.primitive_ico_sphere_add",floor+"\nbpy.ops.mesh.primitive_ico_sphere_add",1)
render=render.replace("frames=range(300) if '--full' in args else [12,24,36,48,60,75,90,120]", "frames=range(390) if '--full' in args else list(range(0,390,6))+[389] if '--preview' in args else [0,18,42,66,90,114,144,180,234,270,300,354,389]")
render=render.replace("for f in frames:","if '--floor-check' in args:\n frames=[0,180,300,389];out=O/'floor-check';out.mkdir(exist_ok=True)\nfor f in frames:")
render=render.replace("for f in frames:","if '--impact-check' in args:\n frames=[270,288,300,324,354,389];out=O/'impact-final';out.mkdir(exist_ok=True)\nfor f in frames:")
render=render.replace("for phase,omega,offset in wave_phases:","retreat=max(0,min(1,(f/30-8.7)/2.3));retreat=retreat*retreat*(3-2*retreat);cam.location=(.25,-17.2-2.0*retreat,5.1+.4*retreat);cam.rotation_euler=(Vector((0,0,1.55))-cam.location).to_track_quat('-Z','Y').to_euler()\n for phase,omega,offset in wave_phases:")
(R/'sigil_02_ground_water_render.py').write_text(render)
print('Wrote grounded water mesh/render entry points.')
