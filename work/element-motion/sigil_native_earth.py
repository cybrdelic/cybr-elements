"""Original stone meshes and shaders; Bullet springs collect them into a sigil."""
import bpy, json, math, random, sys, time, ast
import numpy as np
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parent;B=R/'sigil-native'
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
variant=args[0] if args else '01'; preview='--preview' in args
src=np.load(B/f'earth-{variant}-sources.npz');rng=random.Random(6271)
centers=src['centers'];radii=src['radii'];births=np.round(src['births']*30).astype(int)+1;starts=src['starts'];vels=src['velocities']
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.fps=30;s.frame_end=330;s.gravity=(0,0,-.5)
s.keyframe_insert('gravity',frame=1);s.keyframe_insert('gravity',frame=246);s.gravity=(0,0,-9.81);s.keyframe_insert('gravity',frame=255)
s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=24;s.cycles.use_denoising=True;s.cycles.max_bounces=6
s.render.threads_mode='FIXED';s.render.threads=3;s.render.resolution_x=1280;s.render.resolution_y=720;s.render.resolution_percentage=100
s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=95;s.view_settings.view_transform='AgX'
s.world.use_nodes=True;s.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(0,0,0,1);s.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=0
original=(R/'bending-earth-v5.py').read_text();tree=ast.parse(original);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='material');exec(ast.get_source_segment(original,fn))
rockMats=[material('Slate interior',(.055,.038,.022)),material('Fresh fracture',(.085,.064,.038)),material('Weathered seams',(.018,.012,.007)),material('Mineral inclusion',(.10,.085,.057))]
invisible=bpy.data.materials.new('Invisible collision hull');invisible.use_nodes=True;nt=invisible.node_tree;nt.nodes.clear();tr=nt.nodes.new('ShaderNodeBsdfTransparent');mo=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(tr.outputs[0],mo.inputs['Surface'])
layers=json.loads((R/'layered-rocks-clean.json').read_text());hulls=json.loads((R/'earth-geometry.json').read_text())['pieces'];layerMeshes={};bodies=[]
def rb_add(o):
 bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.rigidbody.object_add();o.select_set(False);return o.rigid_body
def key(o,path,frame):o.keyframe_insert(path,frame=frame)
def linear(o):
 if o.animation_data and o.animation_data.action:
  for fc in o.animation_data.action.fcurves:
   for k in fc.keyframe_points:k.interpolation='CONSTANT' if 'hide_render' in fc.data_path or 'kinematic' in fc.data_path or 'enabled' in fc.data_path else 'LINEAR'
for k,(center,r,b,start,v) in enumerate(zip(centers,radii,births,starts,vels)):
 h=hulls[k%len(hulls)];vs=np.array(h['verts']);centroid=vs.mean(0);radius=np.linalg.norm(vs-centroid,axis=1).max();verts=(vs-centroid)*r/radius
 mesh=bpy.data.meshes.new('Hull');mesh.from_pydata(verts.tolist(),[],h['faces']);mesh.materials.append(invisible)
 o=bpy.data.objects.new(f'Stone {k:04}',mesh);bpy.context.collection.objects.link(o);rb=rb_add(o);rb.mass=max(.01,h['volume']*(r/radius)**3*2700);rb.collision_shape='CONVEX_HULL';rb.use_margin=True;rb.collision_margin=.001;rb.friction=.68;rb.restitution=.04;rb.linear_damping=.12;rb.angular_damping=.18
 far=(40+k*.35,0,-10);o.location=far;key(o,'location',1);key(o,'location',int(b-2));o.location=start-v/30;key(o,'location',int(b-1));o.location=start;key(o,'location',int(b))
 o.rotation_euler=[rng.random()*6 for _ in range(3)];key(o,'rotation_euler',1);rb.kinematic=True;key(rb,'kinematic',1);key(rb,'kinematic',int(b));rb.kinematic=False;key(rb,'kinematic',int(b+1));linear(o)
 family=k%len(layers)
 if family not in layerMeshes:
  q=layers[family];lm=bpy.data.meshes.new(f'Layered fracture {family}');lm.from_pydata(q['verts'],[],q['faces']);lm.update()
  for mat in rockMats:lm.materials.append(mat)
  for face,idx in zip(lm.polygons,q['materials']):face.material_index=int(idx);face.use_smooth=int(idx) not in [1,2]
  layerMeshes[family]=lm
 child=bpy.data.objects.new(f'Layered stone {k:04}',layerMeshes[family]);bpy.context.collection.objects.link(child);child.parent=o;child.scale=(r*(.94+.06*((k*73%101)/100)),r*(.92+.08*((k*43%97)/96)),r)
 child.hide_render=True;key(child,'hide_render',1);key(child,'hide_render',int(b-2));child.hide_render=False;key(child,'hide_render',int(b-1));linear(child)
 am=bpy.data.meshes.new('Anchor');am.from_pydata([(-.002,-.002,-.002),(.002,-.002,-.002),(0,.002,-.002),(0,0,.002)],[],[(0,1,2),(0,3,1),(1,3,2),(2,3,0)])
 anchor=bpy.data.objects.new(f'Anchor {k:04}',am);bpy.context.collection.objects.link(anchor);anchor.hide_render=True;ar=rb_add(anchor);ar.kinematic=True;ar.collision_collections=[False]*19+[True]
 anchor.location=far;key(anchor,'location',1);key(anchor,'location',int(b-2));anchor.location=start-v/30;key(anchor,'location',int(b-1));anchor.location=start;key(anchor,'location',int(b))
 for j in range(1,10):
  u=j/9;u=u*u*(3-2*u);anchor.location=start*(1-u)+center*u;key(anchor,'location',int(b+j))
 linear(anchor)
 joint=bpy.data.objects.new(f'Force {k:04}',None);bpy.context.collection.objects.link(joint);joint.location=far
 bpy.context.view_layer.objects.active=joint;joint.select_set(True);bpy.ops.rigidbody.constraint_add();joint.select_set(False)
 c=joint.rigid_body_constraint;c.type='GENERIC_SPRING';c.spring_type='SPRING2';c.object1=anchor;c.object2=o;c.disable_collisions=True
 for axis in 'xyz':
  setattr(c,'use_spring_'+axis,True);setattr(c,'spring_stiffness_'+axis,rb.mass*(math.tau*8)**2);setattr(c,'spring_damping_'+axis,rb.mass*(math.tau*8)*1.6)
 c.enabled=True;key(c,'enabled',1);key(c,'enabled',246);c.enabled=False;key(c,'enabled',247);linear(joint)
 bodies.append(o)
 if k%200==0:print('CREATED',k,flush=True)
bpy.ops.mesh.primitive_plane_add(size=100,location=(0,0,-3));floor=bpy.context.object;rb_add(floor).type='PASSIVE';floor.rigid_body.friction=.85;floor.hide_render=True;floor.select_set(False)
s.rigidbody_world.substeps_per_frame=16;s.rigidbody_world.solver_iterations=40;s.rigidbody_world.point_cache.frame_end=330
for name,loc,power,size in [('Key',(-2,-4,3.8),650,2.1),('Rim',(1,2,4),850,3),('Fill',(2,-4,1.2),145,4)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-15,1.903125));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1.903125))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=10.5;s.camera=cam
transforms=[];started=time.time()
for f in range(1,331):
 s.frame_set(f);transforms.append([[*o.matrix_world.translation,*o.matrix_world.to_quaternion()] for o in bodies])
 if f==181 and preview:
  s.render.filepath=str(B/f'earth-{variant}-native-hold.jpg');bpy.ops.render.render(write_still=True)
 if f%30==0:print('FRAME',f,'seconds',round(time.time()-started,1),flush=True)
transforms=np.asarray(transforms,dtype=np.float32);assert np.isfinite(transforms).all()
errors=np.linalg.norm(transforms[180,:,:3]-centers,axis=1);drop=transforms[245,:,2]-transforms[-1,:,2]
report={'bodies':len(bodies),'frames':330,'holdMedianError':float(np.median(errors)),'holdMaxError':float(errors.max()),'releaseMedianDrop':float(np.median(drop)),'model':'Bullet convex hull contacts and critically damped guide springs; forces disabled at 8.2s; original layered rock geometry and shader preserved','seconds':time.time()-started}
np.savez_compressed(B/f'earth-{variant}-native-transforms.npz',transforms=transforms,radii=radii,births=births)
(B/f'earth-{variant}-native-report.json').write_text(json.dumps(report,indent=2));print('RESULT',json.dumps(report),flush=True)
assert np.median(errors)<.08,report
assert np.median(drop)>1,report
