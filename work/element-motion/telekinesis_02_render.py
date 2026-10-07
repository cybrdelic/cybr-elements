"""Telekinesis / 02: authored 3D fracture assembly, sustained field and impulse release.

This is a material-study render, not a physics claim: the force field and the
fragment trajectories are deliberately choreographed to preserve the approved
02 silhouette before the release.
"""
import bpy, json, math, random, sys
from pathlib import Path
from mathutils import Vector, Quaternion

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'telekinesis-02'
FRAMES = OUT / 'frames'
PILOT = OUT / 'pilot'
for folder in (FRAMES, PILOT): folder.mkdir(parents=True, exist_ok=True)
pilot = '--pilot' in sys.argv

scene = bpy.context.scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'JPEG'
scene.render.image_settings.quality = 96
scene.render.fps, scene.frame_end = 30, 300
scene.render.film_transparent = False
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes.get('Background')
bg.inputs['Color'].default_value = (0, 0, 0, 1)
bg.inputs['Strength'].default_value = 0
scene.view_settings.look = 'AgX - Medium High Contrast'

def look_at(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat('-Z', 'Y').to_euler()

def smooth(a, b, x):
    x = max(0.0, min(1.0, (x-a)/(b-a)))
    return x*x*(3-2*x)

def light(name, location, energy, color, size):
    data = bpy.data.lights.new(name, 'AREA'); data.energy = energy; data.shape = 'DISK'; data.color = color; data.shape = 'DISK'; data.size = size
    obj = bpy.data.objects.new(name, data); bpy.context.collection.objects.link(obj); obj.location = location; look_at(obj, (0, 0, 1.45)); return obj

# Shallow camera and black field match the existing elemental studies.
bpy.ops.object.camera_add(location=(0.0, -16.2, 4.75))
camera = bpy.context.object; camera.data.lens = 57; look_at(camera, (0, 0, 1.45)); scene.camera = camera
key = light('cool force key', (-4.6, -4.2, 5.8), 950, (.23, .74, 1.0), 4.5)
rim = light('acid rim', (5.5, 1.8, 4.2), 1200, (.66, 1.0, .16), 3.0)
fill = light('void fill', (0, -1.0, 7.0), 250, (.18, .31, .40), 5.5)

def material(name, color, metallic, roughness):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    p = mat.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = roughness
    noise = mat.node_tree.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 8; noise.inputs['Detail'].default_value = 4
    bump = mat.node_tree.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = .28; bump.inputs['Distance'].default_value = .035
    mat.node_tree.links.new(noise.outputs['Fac'], bump.inputs['Height']); mat.node_tree.links.new(bump.outputs['Normal'], p.inputs['Normal'])
    return mat

body = material('Telekinetic smoked chrome', (.022, .050, .065), .72, .28)
edge = material('Charged fracture edges', (.09, .31, .38), .55, .20)
edge.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (.01, .24, .32, 1)
edge.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.4

# The intact held mark is cut from the approved 02 artwork, not a rectangular
# card. It keeps the signature readable during the telekinetic suspension while
# the dimensional fragments articulate around and then leave it.
sigil_mat = bpy.data.materials.new('Approved 02 telekinetic hold')
sigil_mat.use_nodes = True
nodes = sigil_mat.node_tree.nodes; nodes.clear(); links = sigil_mat.node_tree.links
out = nodes.new('ShaderNodeOutputMaterial'); mix = nodes.new('ShaderNodeMixShader')
transparent = nodes.new('ShaderNodeBsdfTransparent'); emission = nodes.new('ShaderNodeEmission')
image = nodes.new('ShaderNodeTexImage'); image.image = bpy.data.images.load(str(ROOT / '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/artwork-02.png'))
rgb = nodes.new('ShaderNodeRGBToBW'); ramp = nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].position = .018; ramp.color_ramp.elements[1].position = .09
ramp.color_ramp.elements[0].color = (0,0,0,1); ramp.color_ramp.elements[1].color = (1,1,1,1)
emission.inputs['Strength'].default_value = .85
links.new(image.outputs['Color'], rgb.inputs['Color']); links.new(rgb.outputs['Val'], ramp.inputs['Fac'])
links.new(image.outputs['Color'], emission.inputs['Color']); links.new(ramp.outputs['Color'], mix.inputs[0])
links.new(transparent.outputs[0], mix.inputs[1]); links.new(emission.outputs[0], mix.inputs[2]); links.new(mix.outputs[0], out.inputs[0])
try: sigil_mat.surface_render_method = 'DITHERED'
except AttributeError: pass
bpy.ops.mesh.primitive_plane_add(size=2, location=(0, .76, 1.52), rotation=(math.pi/2, 0, 0))
sigil = bpy.context.object; sigil.name = 'Approved 02 held by force'; sigil.scale=(4.9, 2.76, 1); sigil.data.materials.append(sigil_mat)
for frame in range(1, 301, 3):
    sigil.hide_render = frame < 28 or frame > 187
    sigil.scale = (4.9*(.90 + .10*smooth(.7,2.7,frame/30)), 2.76*(.90 + .10*smooth(.7,2.7,frame/30)), 1)
    sigil.keyframe_insert('hide_render', frame=frame); sigil.keyframe_insert('scale', frame=frame)

data = json.loads((ROOT / 'earth-geometry.json').read_text())
pieces = []
random.seed(20802)
for index, row in enumerate(data['pieces']):
    mesh = bpy.data.meshes.new('02 force-fracture')
    mesh.from_pydata(row['verts'], [], row['faces']); mesh.update()
    mesh.materials.append(body); mesh.materials.append(edge)
    front_faces = int(len(mesh.polygons) * .66)
    for face in mesh.polygons:
        face.material_index = 0 if face.index < front_faces else 1
        face.use_smooth = face.index < front_faces
    obj = bpy.data.objects.new(f"02 suspended fragment {index}", mesh); bpy.context.collection.objects.link(obj)
    bevel = obj.modifiers.new('Charged edge bevel', 'BEVEL'); bevel.width = .016; bevel.segments = 2
    target = Vector(row['center'])
    n = Vector((target.x * .42 + math.sin(index*2.17), math.cos(index*1.37)*.24, target.z*.28 + math.sin(index*.73)))
    n.normalize()
    start = target + n * (2.4 + (index % 7)*.16) + Vector((0, 0, .55))
    initial = Quaternion((.74, .21, .39, .50)).normalized().slerp(Quaternion(), (index % 9)/12)
    released = target + n * (7.5 + (index % 8)*.55) + Vector((0, 0, -1.5 + (index % 5)*.7))
    obj.rotation_mode = 'QUATERNION'
    for frame in range(1, 301, 3):
        t = frame / 30
        build = smooth(.0, 2.85, t)
        release = smooth(5.7, 8.4, t)
        jitter = (1-release) * smooth(3.0, 5.3, t)
        position = start.lerp(target, build).lerp(released, release)
        position += Vector((math.sin(t*5.3+index)*.025*jitter, math.cos(t*4.1+index*1.7)*.025*jitter, math.sin(t*6.7+index*.3)*.04*jitter))
        obj.location = position
        obj.rotation_quaternion = initial.slerp(Quaternion(), build).slerp(Quaternion((.92, .06*math.sin(index), .08*math.cos(index), .36)), release)
        # The intact 02 silhouette owns the sustained hold. Fracture geometry
        # enters on the impulse itself, avoiding an unreadable debris pile.
        obj.hide_render = frame < 174
        obj.keyframe_insert('location', frame=frame); obj.keyframe_insert('rotation_quaternion', frame=frame); obj.keyframe_insert('hide_render', frame=frame)
    pieces.append(obj)

# Thin, emissive force rings sit behind the assembly and surge at the cast.
ring_mat = bpy.data.materials.new('Telekinetic wave'); ring_mat.use_nodes = True
rp = ring_mat.node_tree.nodes['Principled BSDF']; rp.inputs['Base Color'].default_value = (.05, .36, .52, 1); rp.inputs['Emission Color'].default_value = (.02, .28, .43, 1); rp.inputs['Emission Strength'].default_value = 6; rp.inputs['Roughness'].default_value = .25
for index, radius in enumerate((1.6, 2.35, 3.25)):
    bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=.013, major_segments=96, minor_segments=8, location=(0, .65, 1.45), rotation=(math.pi/2, 0, 0))
    ring = bpy.context.object; ring.name = f'Force containment ring {index+1}'; ring.data.materials.append(ring_mat)
    for frame in range(1, 301, 3):
        t=frame/30; hold=smooth(2.6,5.65,t); blast=smooth(5.7,7.4,t)
        ring.scale=(1+hold*.05+blast*(3.8+index*1.4),)*3
        ring.hide_render = frame < 58 or frame > 245
        ring.keyframe_insert('scale', frame=frame); ring.keyframe_insert('hide_render', frame=frame)

# Fine motes give the force field depth without an interface overlay.
mote_mat = bpy.data.materials.new('Field motes'); mote_mat.use_nodes = True
mp = mote_mat.node_tree.nodes['Principled BSDF']; mp.inputs['Base Color'].default_value=(.11,.68,.86,1);mp.inputs['Emission Color'].default_value=(.03,.45,.62,1);mp.inputs['Emission Strength'].default_value=4
for index in range(190):
    a=random.random()*math.tau; r=random.uniform(1.2,5.4); z=random.uniform(-1.6,4.2)
    base=Vector((math.cos(a)*r, random.uniform(-.5,1.1), z))
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=random.uniform(.008,.028), location=base)
    mote=bpy.context.object; mote.data.materials.append(mote_mat)
    for frame in range(1,301,5):
        t=frame/30; pulse=smooth(5.7,7.5,t); angle=a+t*(.22+index%4*.07)+pulse*1.8
        scale=1+pulse*(3.5+index%5)
        mote.location=(math.cos(angle)*r*scale, base.y+math.sin(t*1.9+index)*.16, z+(t-3.8)*.08+pulse*(z-1.4)*.65)
        mote.scale=(1+pulse*1.8,)*3; mote.keyframe_insert('location',frame=frame);mote.keyframe_insert('scale',frame=frame)

scene.use_nodes = True
nodes=scene.node_tree.nodes; nodes.clear(); links=scene.node_tree.links
layer=nodes.new('CompositorNodeRLayers'); glare=nodes.new('CompositorNodeGlare'); glare.glare_type='FOG_GLOW'; glare.quality='HIGH'; glare.threshold=.45; glare.size=7
composite=nodes.new('CompositorNodeComposite'); links.new(layer.outputs['Image'],glare.inputs['Image']); links.new(glare.outputs['Image'],composite.inputs['Image'])

selected = [45, 120, 180, 225]
render_frames = selected if pilot else range(1,301)
for frame in render_frames:
    scene.frame_set(frame)
    scene.render.filepath = str((PILOT if pilot else FRAMES) / f'{frame:04}.jpg')
    bpy.ops.render.render(write_still=True)
    print(f'FRAME {frame}', flush=True)

(OUT / ('pilot-report.json' if pilot else 'render-report.json')).write_text(json.dumps({
    'element':'telekinesis','frames':list(render_frames) if pilot else 300,'resolution':[1920,1080],'fps':30,
    'method':'Authored 3D fracture assembly, force rings, field motes and choreographed impulse release; no claim of physical telekinesis.'
},indent=2))
