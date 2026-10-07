"""CYBR Elements 02 / telekinesis: authored force assembly and directional cast.

The approved 02 silhouette is made of the same closed, interlocking 3D
fractures used by the coherent Earth study. Motion is deliberately directed;
it is a visual force study, not a physical telekinesis simulation.
"""
import bpy
import json
import math
import random
import sys
from pathlib import Path
from mathutils import Vector, Quaternion

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'telekinesis-02-v3'
PILOT = '--pilot' in sys.argv
DEST = OUT / ('pilot' if PILOT else 'frames')
DEST.mkdir(parents=True, exist_ok=True)
DATA = json.loads((ROOT / 'sigil-02-coherent/earth-geometry.json').read_text())
assert len(DATA['pieces']) >= 150
random.seed(90202)

def smooth(a, b, x):
    u = max(0.0, min(1.0, (x-a)/(b-a)))
    return u*u*(3.0-2.0*u)

def aim(obj, point):
    obj.rotation_euler = (Vector(point)-obj.location).to_track_quat('-Z','Y').to_euler()

def area(name, position, target, energy, color, diameter):
    lamp = bpy.data.lights.new(name,'AREA')
    lamp.shape = 'DISK'; lamp.energy = energy; lamp.color = color; lamp.size = diameter
    obj = bpy.data.objects.new(name,lamp); bpy.context.collection.objects.link(obj)
    obj.location = position; aim(obj,target)
    return obj

bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1920; scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100; scene.render.fps = 30
scene.render.image_settings.file_format = 'JPEG'; scene.render.image_settings.quality = 97
scene.render.film_transparent = False
scene.view_settings.view_transform = 'AgX'
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0,0,0,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0

bpy.ops.object.camera_add(location=(.65,-16.8,4.2375))
cam = bpy.context.object; cam.data.lens = 44; cam.data.sensor_width = 36
aim(cam,(0,0,2.8875)); scene.camera = cam
area('large neutral key',(-3.2,-5.2,6.4),(0,0,2.5),1150,(.83,.87,1),4.5)
area('violet edge',(3.3,1.8,5.0),(0,0,2.6),920,(.52,.37,1),3.4)
area('low silver fill',(4.0,-4.5,1.2),(0,0,2.3),270,(.71,.78,1),5.0)
pressure = bpy.data.lights.new('moving telekinetic pressure','POINT')
pressure.color=(.46,.28,1); pressure.shadow_soft_size=.7
pressure_obj=bpy.data.objects.new('moving telekinetic pressure',pressure)
bpy.context.collection.objects.link(pressure_obj)
for f,x,power in [(1,-5,0),(55,-4.5,35),(100,-1.3,68),
                  (150,2.7,48),(180,-4.0,10),(197,-2.5,160),
                  (219,4.2,100),(250,8,0),(300,9,0)]:
    pressure_obj.location=(x,-.6,2.7)
    pressure.energy=power
    pressure_obj.keyframe_insert('location',frame=f)
    pressure.keyframe_insert('energy',frame=f)

def finish_material(name, base, metal, rough, edge=False):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    nodes = mat.node_tree.nodes; links = mat.node_tree.links
    p = nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*base,1)
    p.inputs['Metallic'].default_value = metal
    p.inputs['Roughness'].default_value = rough
    tex = nodes.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value = 27 if edge else 12
    tex.inputs['Detail'].default_value = 3
    bump = nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = .16
    bump.inputs['Distance'].default_value = .007 if edge else .012
    links.new(tex.outputs['Fac'],bump.inputs['Height'])
    links.new(bump.outputs['Normal'],p.inputs['Normal'])
    if edge:
        p.inputs['Emission Color'].default_value = (.027,.012,.075,1)
        p.inputs['Emission Strength'].default_value = .28
    return mat

face_mat = finish_material('satin mineral / silver graphite',(.085,.09,.105),.55,.34)
edge_mat = finish_material('violet fracture interior',(.052,.035,.095),.30,.48,True)
fragment_objects=[]

for row in DATA['pieces']:
    k = row['seed']; target = Vector(row['center'])
    mesh = bpy.data.meshes.new('approved 02 closed fracture')
    mesh.from_pydata(row['verts'],[],row['faces']); mesh.update()
    mesh.materials.append(face_mat); mesh.materials.append(edge_mat)
    for poly in mesh.polygons:
        poly.material_index = 0 if poly.index < row['frontFaces'] else 1
        poly.use_smooth = poly.index < row['frontFaces']*2
    obj = bpy.data.objects.new(f'02 telekinetic fragment {k:03}',mesh)
    bpy.context.collection.objects.link(obj)
    fragment_objects.append(obj)
    bevel = obj.modifiers.new('slender broken bevel','BEVEL'); bevel.width=.008; bevel.segments=2
    obj.rotation_mode='QUATERNION'
    direction = Vector((.45*math.sin(k*1.77)+target.x*.12,
                        .35*math.cos(k*2.12),
                        .35*math.sin(k*.83)+.26))
    direction.normalize()
    start = target + direction*(1.3+.22*(k%9))
    initial = Quaternion((.88,.18*math.sin(k),.16*math.cos(k),.17)).normalized()
    cast_dir = Vector((1.0, .18*math.sin(k*.72), .15*math.cos(k*.89)))
    cast_dir.normalize()
    for f in range(1,301,3):
        t=(f-1)/30
        arrival=.45+(target.x+4.1)*.095
        assemble=smooth(arrival,arrival+2.15,t)
        wave_start=6.15+(target.x+4.1)*.055
        launch=smooth(wave_start,wave_start+1.65,t)
        held=smooth(2.4,3.3,t)*(1-launch)
        pressure_wave=.08*math.exp(-((t-(3.55+target.x*.18))/.23)**2)*held
        wobble=Vector((.014*math.sin(t*5.2+k*.6)+pressure_wave,
                       .065*math.sin(t*3.9+k*.21),
                       .022*math.cos(t*4.7+k*.43)))*held
        cast=cast_dir*(7.2+.31*(k%8))*launch*launch
        cast += Vector((0,.16*math.sin(k),-.7*launch*launch))
        obj.location=start.lerp(target,assemble)+wobble+cast
        obj.rotation_quaternion=initial.slerp(Quaternion(),assemble).slerp(
            Quaternion((.90,.14*math.sin(k),.18*math.cos(k),.30)).normalized(),launch)
        obj.keyframe_insert('location',frame=f)
        obj.keyframe_insert('rotation_quaternion',frame=f)

# The force must be visible *within the approved silhouette*, not in an
# unrelated perimeter ring. Short channels bridge neighboring fragments;
# broken wisps leak from the outermost tips into the surrounding black.
def field_material(name, color, strengths):
    mat=bpy.data.materials.new(name); mat.use_nodes=True
    nodes=mat.node_tree.nodes; nodes.clear()
    links=mat.node_tree.links
    emission=nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value=(*color,1)
    output=nodes.new('ShaderNodeOutputMaterial')
    links.new(emission.outputs['Emission'],output.inputs['Surface'])
    for frame,strength in strengths:
        emission.inputs['Strength'].default_value=strength
        emission.inputs['Strength'].keyframe_insert('default_value',frame=frame)
    return mat

field_timing=[(1,0),(25,.15),(65,1.1),(100,3.4),(150,4.2),
              (182,5.1),(195,10),(208,7),(223,1.3),(245,0),(300,0)]
shell_mat=field_material('purple contour leakage',(.30,.055,.68),field_timing)
tether_mat=field_material('white-violet interfragment force',(.42,.29,.95),
                          [(f,s*.86) for f,s in field_timing])
aura_mat=field_material('fragment-bound pressure sheath',(.26,.08,.75),
                        [(f,s*.42) for f,s in field_timing])
for i,fragment in enumerate(fragment_objects):
    aura_mesh=fragment.data.copy()
    aura_mesh.materials.clear(); aura_mesh.materials.append(aura_mat)
    aura=bpy.data.objects.new(f'force sheath on fragment {i:03}',aura_mesh)
    bpy.context.collection.objects.link(aura)
    aura.parent=fragment
    aura.location=(0,.13,0)
    aura.scale=(1.075,1.0,1.075)

field_root=bpy.data.objects.new('breathing telekinetic volume',None)
bpy.context.collection.objects.link(field_root)
for frame,angle,scale in [(1,-.015,.96),(65,.018,1.0),(110,-.012,1.025),
                          (155,.013,.985),(185,-.018,1.03),(210,.02,1.05),
                          (235,.04,1.10),(300,.04,1.10)]:
    field_root.rotation_euler[1]=angle
    field_root.scale=(scale,1,scale)
    field_root.keyframe_insert('rotation_euler',frame=frame)
    field_root.keyframe_insert('scale',frame=frame)

def filament(name,coordinates,width,material,parent=field_root):
    curve=bpy.data.curves.new(name,'CURVE'); curve.dimensions='3D'
    curve.resolution_u=2; curve.bevel_depth=width; curve.bevel_resolution=2
    curve.use_fill_caps=True
    spline=curve.splines.new('POLY'); spline.points.add(len(coordinates)-1)
    for j,(x,y,z) in enumerate(coordinates):
        spline.points[j].co=(x,y,z,1)
        spline.points[j].radius=max(.06,math.sin(math.pi*j/(len(coordinates)-1)))
    curve.materials.append(material)
    obj=bpy.data.objects.new(name,curve)
    bpy.context.collection.objects.link(obj); obj.parent=parent
    return obj

field_rng=random.Random(11092)
centers=[Vector(row['center']) for row in DATA['pieces']]
connected=set()
for i,a in enumerate(centers):
    neighbors=sorted((math.hypot(a.x-b.x,a.z-b.z),j)
                     for j,b in enumerate(centers) if j!=i)
    for _,j in neighbors[:2]:
        pair=tuple(sorted((i,j)))
        if pair in connected or (i+j)%5==0: continue
        connected.add(pair)
        b=centers[j]
        front=-.27 if (i+j)%4==0 else .22
        start=Vector((a.x,front,a.z))
        end=Vector((b.x,front,b.z))
        delta=end-start
        side=Vector((-delta.z,0,delta.x)).normalized()
        bow=side*field_rng.uniform(-.11,.11)
        pts=[]
        for k in range(13):
            u=k/12
            pos=start.lerp(end,u)+bow*math.sin(math.pi*u)
            pos.y+=.06*math.sin(math.pi*u)
            pts.append(tuple(pos))
        filament(f'interfragment pressure link {i:03}-{j:03}',pts,
                 field_rng.uniform(.006,.011),tether_mat)

for i in range(90):
    seed=(i*29+7)%len(centers)
    a=centers[seed]
    outward=Vector((a.x*.34+field_rng.uniform(-.5,.5),0,
                    (a.z-2.7)*.8+field_rng.uniform(-.35,.35)))
    if outward.length<.15: continue
    outward.normalize()
    reach=field_rng.uniform(.20,.62)
    front=-.30 if i%3==0 else .20
    start=Vector((a.x,front,a.z))
    bend=Vector((-outward.z,0,outward.x))*field_rng.uniform(-.15,.15)
    pts=[]
    for k in range(14):
        u=k/13
        pos=start+outward*(reach*u)+bend*math.sin(math.pi*u)
        pos.y+=.08*math.sin(u*math.pi*1.7)
        pts.append(tuple(pos))
    filament(f'fracture-tip field leak {i:02}',pts,
             field_rng.uniform(.005,.012),shell_mat)

# These pressure contours are sampled from offsets of the approved source
# signed-distance field. Intermittent paths follow its actual strokes and
# counters, never an unrelated ellipse or a straight electrical arc.
contour_data=json.loads((ROOT/'sigil-02-coherent/telekinesis-field-contours.json').read_text())
for level_i,level in enumerate(contour_data['levels']):
    for path_i,path in enumerate(level['paths']):
        step=9 if level_i==0 else 12
        for start in range(0,len(path)-2,step):
            if field_rng.random() < (.22+.13*level_i): continue
            section=path[start:min(start+step+3,len(path))]
            if len(section)<4: continue
            phase=field_rng.uniform(0,math.tau)
            pts=[(x+.018*math.sin(j*.73+phase),
                  -.34-.06*level_i+.045*math.sin(j*.52+phase),
                  z+.014*math.cos(j*.6+phase))
                 for j,(x,z) in enumerate(section)]
            filament(f'sigil pressure contour {level_i}-{path_i}-{start}',pts,
                     .006+.003*level_i,shell_mat)

# Sparse illuminated dust stays close to the mark. It responds to the same
# left-to-right impulse without drawing graphic rings or interface symbols.
dust_mat=bpy.data.materials.new('suspended field dust'); dust_mat.use_nodes=True
dp=dust_mat.node_tree.nodes['Principled BSDF']
dp.inputs['Base Color'].default_value=(.34,.30,.55,1)
dp.inputs['Emission Color'].default_value=(.11,.07,.24,1)
dp.inputs['Emission Strength'].default_value=1.6
for i in range(190):
    x=random.uniform(-4.1,4.1); z=random.uniform(.65,4.0)
    y=random.uniform(-.60,.80); radius=random.uniform(.004,.015)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=radius,location=(x,y,z))
    mote=bpy.context.object; mote.name=f'field dust {i:03}'; mote.data.materials.append(dust_mat)
    for f in range(1,301,5):
        t=(f-1)/30; launch=smooth(6.1+(x+4.1)*.055,7.9,t)
        mote.location=(x+.055*math.sin(t*1.7+i)+launch*8.0,
                       y+.085*math.sin(t*1.15+i*.6),
                       z+.065*math.cos(t*1.4+i*.2)-launch*.5)
        mote.keyframe_insert('location',frame=f)

scene.use_nodes=True
nodes=scene.node_tree.nodes; nodes.clear(); links=scene.node_tree.links
layer=nodes.new('CompositorNodeRLayers')
glare=nodes.new('CompositorNodeGlare'); glare.glare_type='FOG_GLOW'
glare.threshold=1.15; glare.quality='HIGH'; glare.mix=-.7
out=nodes.new('CompositorNodeComposite')
links.new(layer.outputs['Image'],glare.inputs['Image'])
links.new(glare.outputs['Image'],out.inputs['Image'])

frame_slice=next((arg.split('=',1)[1] for arg in sys.argv if arg.startswith('--frames=')),None)
if frame_slice:
    first,last=map(int,frame_slice.split('-'))
    assert 1<=first<=last<=300
    frames=range(first,last+1)
else:
    frames=[37,105,150,187,216,258] if PILOT else range(1,301)
for f in frames:
    scene.frame_set(f); scene.render.filepath=str(DEST/f'{f:04}.jpg')
    bpy.ops.render.render(write_still=True)
    if PILOT or f%30==0: print(f'TELEKINESIS FRAME {f}',flush=True)
(OUT/('pilot-report.json' if PILOT else 'render-report.json')).write_text(json.dumps({
    'source':'approved 02 coherent fracture geometry',
    'pieces':len(DATA['pieces']), 'frames':list(frames) if PILOT else 300,
    'resolution':[1920,1080], 'fps':30,
    'motion':'authored assembly, visible breathing field and fragment tethers, directional impulse cast',
    'userAccepted':False
},indent=2))
