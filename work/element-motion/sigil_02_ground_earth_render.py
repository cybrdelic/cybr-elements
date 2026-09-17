"""Guided fracture assembly, sustained silhouette, then native Bullet release."""
import bpy,json,math,sys,time,random
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parent;O=R/'sigil-02-bending-ground';full='--full' in sys.argv
out=O/('earth-frames' if full else 'earth-pilot');out.mkdir(exist_ok=True)
if '--floor-check' in sys.argv:out=O/'earth-ground-check-v4';out.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
if '--release-check' in sys.argv:out=O/'earth-release-check';out.mkdir(exist_ok=True)
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.device='GPU' if full else 'CPU';s.cycles.samples=48 if full else 12;s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.max_bounces=6;s.render.use_persistent_data=True;s.render.threads_mode='FIXED';s.render.threads=2
s.render.resolution_x=1920 if full else 960;s.render.resolution_y=1080 if full else 540;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=97;s.render.fps=30;s.frame_end=390;s.gravity=(0,0,-9.81);s.view_settings.view_transform='AgX'
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'
s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs['Color'].default_value=(0,0,0,1);s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=0
m=bpy.data.materials.new('Photogrammetry stone / continuous fractured surface');m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF')
texroot=R/'sigil-02-repair/scans/rock_09/textures'
if not texroot.exists():texroot=R/'sigil-02-repair/scans/rock_09'
def image_node(filename,noncolor=False):
 t=n.new('ShaderNodeTexImage');t.image=bpy.data.images.load(str(next((R/'sigil-02-repair/scans/rock_09').rglob(filename))))
 if noncolor:t.image.colorspace_settings.name='Non-Color'
 t.extension='REPEAT';return t
diff=image_node('rock_09_diff_2k.jpg');arm=image_node('rock_09_arm_2k.jpg',True);normal=image_node('rock_09_nor_gl_2k.jpg',True)
tint=n.new('ShaderNodeMixRGB');tint.blend_type='MULTIPLY';tint.inputs[0].default_value=.48;tint.inputs[2].default_value=(.62,.48,.30,1);l.new(diff.outputs['Color'],tint.inputs[1]);l.new(tint.outputs[0],p.inputs['Base Color'])
sep=n.new('ShaderNodeSeparateColor');l.new(arm.outputs['Color'],sep.inputs[0]);l.new(sep.outputs['Green'],p.inputs['Roughness']);nm=n.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=.7;l.new(normal.outputs['Color'],nm.inputs['Color']);l.new(nm.outputs[0],p.inputs['Normal'])
side=m.copy();side.name='Fresh fracture / darker mineral';side.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.9
def smooth(x):
 x=max(0,min(1,x));return x*x*(3-2*x)

data=json.loads((R/'sigil-02-coherent/earth-geometry.json').read_text());objects=[]
for row in data['pieces']:
 me=bpy.data.meshes.new('Interlocking fracture');me.from_pydata(row['verts'],[],row['faces']);me.update();o=bpy.data.objects.new(f'Fracture {row["seed"]:03}',me);bpy.context.collection.objects.link(o);me.materials.append(m);me.materials.append(side)
 uv=me.uv_layers.new(name='Continuous geological coordinates');center=Vector(row['center']);k=row['seed']
 for poly in me.polygons:
  poly.material_index=0 if poly.index<row['frontFaces'] else 1
  poly.use_smooth=poly.index<row['frontFaces']*2
  for li in poly.loop_indices:
   v=me.vertices[me.loops[li].vertex_index].co+center;uv.data[li].uv=(v.x*.65,v.z*.65)
 bevel=o.modifiers.new('Small chipped edges','BEVEL');bevel.width=.007;bevel.segments=2
 o.location=center;bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.rigidbody.object_add();o.select_set(False);rb=o.rigid_body;rb.collision_shape='CONVEX_HULL';rb.use_margin=True;rb.collision_margin=.001;rb.mass=max(.005,row['volume']*2600);rb.friction=.78;rb.restitution=.025;rb.linear_damping=.08;rb.angular_damping=.12
 # Every full-size fracture is visible from the first frame, lying on the
 # floor. Its powered trajectory lifts and rolls it several world units.
 u=max(0,min(1,(center.x+4.05)/8.1));release=244
 startRotation=Vector((1.35+.45*math.sin(k*1.7),.55*math.sin(k*2.3),k*2.399))
 o.rotation_euler=startRotation
 rot=o.rotation_euler.to_matrix();bottom=min((rot@v.co).z for v in me.vertices)
 start=Vector((-3.7+7.4*u+.18*math.sin(k),1.35*math.sin(k*2.399),-bottom+.022))
 middle=Vector((-3.95+7.85*u,.85*math.sin(u*math.pi*2-.6),1.35+1.7*math.sin(math.pi*(u*.9+.08))))
 for f in range(1,163,2):
  t=(f-1)/30;a=smooth((t-.5-u*.55)/2.0);b=smooth((t-2.3-u*.5)/2.35)
  o.location=start.lerp(middle,a).lerp(center,b)
  o.rotation_euler=tuple((1-b)*(startRotation[j]+a*(2.0 if j==0 else -.7)*math.sin(k*.4+j)) for j in range(3))
  o.keyframe_insert('location',frame=f);o.keyframe_insert('rotation_euler',frame=f)
 o.location=center;o.rotation_euler=(0,0,0);o.keyframe_insert('location',frame=166);o.keyframe_insert('rotation_euler',frame=166)
 for f in range(169,release,3):
  gain=min(1,(f-166)/16)*(1-smooth((f-228)/12));wave=f*.062-center.x*.87+center.z*.35
  o.location=center+Vector((.012*math.sin(wave)+.006*math.sin(f*.13+k),.16*math.sin(wave)+.045*math.sin(f*.081+k*.41),.018*math.cos(wave*.87+k*.09)))*gain
  o.rotation_euler=(gain*.10*math.sin(wave+k*.83),gain*.12*math.sin(wave*.81+k*.37),gain*.045*math.cos(wave+k*.51));o.keyframe_insert('location',frame=f);o.keyframe_insert('rotation_euler',frame=f)
 # Settle the powered stress wave before handing all fragments to Bullet.
 # A simultaneous, nonoverlapping handoff avoids collision-correction pops.
 o.location=center;o.rotation_euler=(0,0,0);o.keyframe_insert('location',frame=241);o.keyframe_insert('rotation_euler',frame=241)
 o.keyframe_insert('location',frame=release);o.keyframe_insert('rotation_euler',frame=release)
 rb.kinematic=True;rb.keyframe_insert('kinematic',frame=1);rb.keyframe_insert('kinematic',frame=release);rb.kinematic=False;rb.keyframe_insert('kinematic',frame=release+1)
 for fc in o.animation_data.action.fcurves:
  for key in fc.keyframe_points:key.interpolation='CONSTANT' if fc.data_path=='rigid_body.kinematic' else 'LINEAR'
 objects.append(o)
# Small irregular gravel on the stage supplies a contact-scale cue. All of
# it exists at frame one and uses Bullet for the full shot.
rng=random.Random(97213)
for chip_index in range(92):
 radius=min(.065,.009/(1-rng.random()*.985)**.52)
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=radius,location=(rng.uniform(-4.2,4.2),rng.uniform(-1.4,1.4),radius*1.3));o=bpy.context.object;o.name=f'Ground gravel {chip_index:03}'
 for vert in o.data.vertices:vert.co*=rng.uniform(.72,1.25)
 o.data.materials.append(side);bpy.ops.rigidbody.object_add();rb=o.rigid_body;rb.collision_shape='CONVEX_HULL';rb.use_margin=True;rb.collision_margin=.0004;rb.mass=max(.0005,4/3*math.pi*radius**3*2600);rb.friction=.8;rb.restitution=.05;rb.linear_damping=.05;rb.angular_damping=.15;o.select_set(False);objects.append(o)
# Visible floor and actual passive Bullet collision geometry are the same mesh.
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,-.1));floor=bpy.context.object;floor.name='Ground / passive contact body';floor.scale=(40,40,.2);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
fm=bpy.data.materials.new('Black ground / stone contact');fm.use_nodes=True;fp=fm.node_tree.nodes.get('Principled BSDF');fp.inputs['Base Color'].default_value=(.009,.009,.009,1);fp.inputs['Roughness'].default_value=.8;fp.inputs['Specular IOR Level'].default_value=0;floor.data.materials.append(fm)
bpy.ops.rigidbody.object_add();floor.rigid_body.type='PASSIVE';floor.rigid_body.collision_shape='BOX';floor.rigid_body.use_margin=True;floor.rigid_body.collision_margin=.001;floor.rigid_body.friction=.86;floor.rigid_body.restitution=.035
floor.hide_render=True
bpy.ops.mesh.primitive_plane_add(size=40,location=(0,0,0));bpy.context.object.name='Ground / visible contact surface';bpy.context.object.data.materials.append(fm)
s.rigidbody_world.substeps_per_frame=16;s.rigidbody_world.solver_iterations=40;s.rigidbody_world.point_cache.frame_end=390
for name,loc,power,size in [('Soft key',(-3,-5,6),950,4),('Warm rim',(3,2,4.8),700,3),('Broad fill',(4,-4,3.7),180,5)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;d.color=(1,.9,.76) if 'Warm' in name else (1,1,1);o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(.25,-17.2,5.1));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1.55))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=48;cam.data.sensor_width=36;s.camera=cam
s.render.use_motion_blur=True;s.render.motion_blur_shutter=.35;start=time.time();rows=[]
for f in range(1,391):
 s.frame_set(f)
 if f%30==0 or ('--physics-check' in sys.argv and 241<=f<=270):
  dg=bpy.context.evaluated_depsgraph_get();poses=[o.evaluated_get(dg).matrix_world for o in objects];rows.append(dict(frame=f,finite=all(all(math.isfinite(v) for v in a.translation) for a in poses),minZ=min(a.translation.z for a in poses),nearFloor=sum(a.translation.z<.5 for a in poses),maxRise=max([a.translation.z-row['center'][2] for a,row in zip(poses,data['pieces'])])))
 if '--physics-check' not in sys.argv and ((f in [229,244,249,255,261,270,300,390] if '--release-check' in sys.argv else full) or ('--release-check' not in sys.argv and (f in [1,91,181,271,301,390] if '--floor-check' in sys.argv else f in [1,19,43,67,91,115,145,181,235,271,301,355,390]))) and not (out/f'{f-1:04}.jpg').exists():
  s.render.filepath=str(out/f'{f-1:04}.jpg');bpy.ops.render.render(write_still=True)
 if f%30==0:print('EARTH',f,round(time.time()-start,1),flush=True)
(O/('earth-physics-check.json' if '--physics-check' in sys.argv else 'earth-report.json' if full else 'earth-pilot-report.json')).write_text(json.dumps(dict(frames=390,pieces=len(objects),method='All fractures visible on the ground at frame one; authored curved powered lift and hold; native Bullet inter-body and floor collisions after release. Ground gravel is dynamic throughout. Same scanned rock material.',rows=rows),indent=2))
print('EARTH COMPLETE',flush=True)
