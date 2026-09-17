import bpy,json,math,random,time,sys
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from shared_motion import pose,DATA
random.seed(6271);data=json.loads((R/'earth-geometry.json').read_text());out=R/'earth-packed-frames';out.mkdir(exist_ok=True)
s=bpy.context.scene;bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);s.render.engine='BLENDER_EEVEE_NEXT';s.render.threads_mode='FIXED';s.render.threads=3;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=94;s.render.fps=30;s.frame_end=120;s.world.color=(0,0,0);s.world.use_nodes=True;s.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(0,0,0,1);s.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=0;s.view_settings.view_transform='AgX'
# Authored earthbending lift during the shared writing beat; full gravity on release.
s.gravity=(0,0,-.5);s.keyframe_insert('gravity',frame=1);s.keyframe_insert('gravity',frame=51);s.gravity=(0,0,-9.81);s.keyframe_insert('gravity',frame=65)
def material(name,color):
 m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=(*color,1);n.inputs['Roughness'].default_value=.92
 noise=m.node_tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=22;noise.inputs['Detail'].default_value=3;bump=m.node_tree.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.28;bump.inputs['Distance'].default_value=.018;m.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height']);m.node_tree.links.new(bump.outputs['Normal'],n.inputs['Normal']);return m
mats=[material('Stone '+str(i),(.09+i*.010,.060+i*.008,.032+i*.006)) for i in range(5)];floorMat=material('Ground',(.008,.009,.010))
bpy.ops.mesh.primitive_plane_add(size=100);floor=bpy.context.object;floor.data.materials.append(floorMat);bpy.ops.rigidbody.object_add();floor.rigid_body.type='PASSIVE';floor.rigid_body.friction=.85;floor.select_set(False)
births=[];spawned=[]
for k in range(180):
 b=4+int(k*47/180);t=(b-1)/30;p,d,on,speed=pose(t);r=min(.185,.070/(max(.035,random.random())**.34));a=random.random()*math.tau;offset=random.random()**.5*.18
 center=Vector((float(p[0]-d[1]*math.cos(a)*offset),math.sin(a)*offset,float(p[1]+d[0]*math.cos(a)*offset)));vel=Vector((float(d[0])*1.6,random.uniform(-.14,.14),float(d[1])*1.6))
 # Reject overlaps at emission instead of letting Bullet explosively separate intersecting stones.
 for attempt in range(100):
  angle=random.random()*math.tau;cross=random.random()**.5*.25;along=random.uniform(-.055,.055)
  candidate=Vector((float(p[0]-d[1]*math.cos(angle)*cross+d[0]*along),math.sin(angle)*cross,float(p[1]+d[0]*math.cos(angle)*cross+d[1]*along)))
  clear=True
  for ot,op,ov,orr in spawned:
   age=t-ot
   if age>1.2:continue
   predicted=op+ov*age+Vector((0,0,-.25*age*age))
   if (candidate-predicted).length<r+orr+.006:clear=False;break
  if clear:break
  if attempt in [35,65,85]:r*=.85
 center=candidate;spawned.append((t,center.copy(),vel.copy(),r))
 src=data['pieces'][k%len(data['pieces'])];vs=[Vector(v) for v in src['verts']];centroid=sum(vs,Vector())/len(vs);radius=max((v-centroid).length for v in vs);vs=[(v-centroid)*(r/radius) for v in vs]
 me=bpy.data.meshes.new('Convex stone');me.from_pydata(vs,[],src['faces']);me.update();o=bpy.data.objects.new('Emitted stone '+str(k),me);bpy.context.collection.objects.link(o);o.data.materials.append(mats[k%len(mats)]);bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.rigidbody.object_add();o.select_set(False);rb=o.rigid_body;rb.mass=max(.01,src['volume']*(r/radius)**3*2700);rb.collision_shape='CONVEX_HULL';rb.use_margin=True;rb.collision_margin=.001;rb.friction=.68;rb.restitution=.12;rb.linear_damping=.035;rb.angular_damping=.08
 o.location=(50+k*.5,0,-10);o.keyframe_insert('location',frame=1);o.hide_render=True;o.keyframe_insert('hide_render',frame=1);o.keyframe_insert('hide_render',frame=b-2)
 o.location=center-vel/30;o.keyframe_insert('location',frame=b-1);o.hide_render=False;o.keyframe_insert('hide_render',frame=b-1);o.location=center;o.keyframe_insert('location',frame=b)
 o.rotation_euler=[random.random()*6 for _ in range(3)];o.keyframe_insert('rotation_euler',frame=b-1);o.rotation_euler.rotate_axis('Y',random.uniform(-.08,.08));o.keyframe_insert('rotation_euler',frame=b)
 rb.kinematic=True;rb.keyframe_insert('kinematic',frame=1);rb.keyframe_insert('kinematic',frame=b);rb.kinematic=False;rb.keyframe_insert('kinematic',frame=b+1)
 for fc in o.animation_data.action.fcurves:
  for key in fc.keyframe_points:key.interpolation='CONSTANT' if fc.data_path in ['hide_render','rigid_body.kinematic'] else 'LINEAR'
 births.append({'frame':b,'source':p.tolist(),'center':list(center),'velocity':list(vel),'radius':r})
s.rigidbody_world.substeps_per_frame=8;s.rigidbody_world.solver_iterations=20;s.rigidbody_world.point_cache.frame_end=120
for name,loc,power,size in [('Key',(-2,-4,6),450,5),('Rim',(1,2,4),650,4)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-15,DATA['camera']['center'][1]));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,DATA['camera']['center'][1]))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=DATA['camera']['width'];s.camera=cam
start=time.time()
for f in range(1,121):
 s.frame_set(f);s.render.filepath=str(out/f'{f-1:04}.jpg');bpy.ops.render.render(write_still=True)
 if f%15==0:print('FRAME',f,'seconds',round(time.time()-start,1),flush=True)
(R/'earth-refined-report.json').write_text(json.dumps({'births':births,'frames':120,'fps':30,'trail':'shared-trail.json','lift':'Effective gravity .5 m/s2 during drawing, ramp to 9.81 after frame 51; Bullet free release and contacts','camera':DATA['camera']}))
