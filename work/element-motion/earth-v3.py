import bpy,sys,json,math,time
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parent;data=json.loads((R/'earth-geometry.json').read_text());out=R/'earth-v3-frames';out.mkdir(exist_ok=True)
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [];full='--full' in args
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=24;s.cycles.use_denoising=True;s.cycles.device='GPU';s.render.threads_mode='FIXED';s.render.threads=3;s.render.resolution_x=1280;s.render.resolution_y=720;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=94;s.render.fps=30;s.frame_end=120
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
s.world.color=(.09,.09,.09)
def mat(name,color,rough):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;return m
stone=mat('Neutral stone clay',(.16,.18,.19),.86);ground=mat('Ground',(.055,.063,.068),.82)
bpy.ops.mesh.primitive_plane_add(size=200);floor=bpy.context.object;floor.data.materials.append(ground);bpy.ops.rigidbody.object_add();floor.rigid_body.type='PASSIVE';floor.rigid_body.friction=.8
pieces=[]
for i,d in enumerate(data['pieces']):
 me=bpy.data.meshes.new('fracture');me.from_pydata(d['verts'],[],d['faces']);me.update();o=bpy.data.objects.new(f'Rock {i}',me);bpy.context.collection.objects.link(o);o.location=d['center'];o.location.z+=.0283;o.data.materials.append(stone);bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.rigidbody.object_add();o.select_set(False);o.rigid_body.mass=max(.2,d['volume']*2700);o.rigid_body.friction=.72;o.rigid_body.restitution=.08;o.rigid_body.collision_shape='CONVEX_HULL';o.rigid_body.use_margin=True;o.rigid_body.collision_margin=.0015;pieces.append(o)
for a,b in data['links']:
 bpy.ops.object.empty_add(location=(pieces[a].location+pieces[b].location)*.5);o=bpy.context.object;bpy.ops.rigidbody.constraint_add();c=o.rigid_body_constraint;c.type='FIXED';c.object1=pieces[a];c.object2=pieces[b];c.use_breaking=True;c.breaking_threshold=350+100*abs(math.sin(a*2+b));c.disable_collisions=True
# A visible moving rock supplies the impact. Subsequent fracture and contact are Bullet dynamics.
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=.65,location=(-6.,0,.66));hammer=bpy.context.object;hammer.name='Incoming rock';hammer.data.materials.append(stone);bpy.ops.rigidbody.object_add();hammer.rigid_body.mass=3100;hammer.rigid_body.kinematic=True;hammer.keyframe_insert('location',frame=1);hammer.location=(-2.5,0,.66);hammer.keyframe_insert('location',frame=16);hammer.location=(1.7,0,.72);hammer.keyframe_insert('location',frame=48);hammer.rigid_body.keyframe_insert('kinematic',frame=16);hammer.rigid_body.kinematic=False;hammer.rigid_body.keyframe_insert('kinematic',frame=17)
if hammer.animation_data:
 for fc in hammer.animation_data.action.fcurves:
  for k in fc.keyframe_points:k.interpolation='LINEAR'
s.rigidbody_world.substeps_per_frame=8;s.rigidbody_world.solver_iterations=30;s.rigidbody_world.point_cache.frame_end=120
def area(name,loc,power,size):
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,.5))-o.location).to_track_quat('-Z','Y').to_euler()
area('Raking key',(-3,-3,5),1200,4);area('Back edge',(2,2,3),850,3)
bpy.ops.object.camera_add(location=(4.8,-8,4.3));cam=bpy.context.object;cam.rotation_euler=(Vector((.15,0,.5))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=38;s.camera=cam;s.view_settings.view_transform='AgX';start=time.time()
for f in range(1,121):
 s.frame_set(f)
 if full or f in [1,25,40,55,80,120]:s.render.filepath=str(out/f'{f:04}.jpg');bpy.ops.render.render(write_still=True);print('FRAME',f,round(time.time()-start,1),flush=True)
(R/'earth-report.json').write_text(json.dumps({'frames':120 if full else [1,25,40,55,80,120],'rigidBodies':len(pieces)+1,'constraints':len(data['links']),'mechanism':'visible impactor; volumetric convex fractures; breakable fixed constraints; friction and gravity; no texture cracks or decorative debris'}))
