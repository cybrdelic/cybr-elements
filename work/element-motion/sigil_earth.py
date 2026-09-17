"""Closed stone fragments assemble under a spring guide, then Bullet release."""
from pathlib import Path
import bpy,sys,json,math,time
import numpy as np
from mathutils import Vector
R=Path(__file__).resolve().parent;args=sys.argv[sys.argv.index('--')+1:];variant=args[0];assert variant in ['01','02'];pilot='--pilot' in args;B=R/'sigil-v1';O=B/f'earth-{variant}';O.mkdir(exist_ok=True);out=O/('pilot' if pilot else 'frames');out.mkdir(exist_ok=True)
with np.load(B/f'earth-{variant}-geometry.npz') as archive:d={k:archive[k] for k in archive.files}
with np.load(B/f'mark-{variant}.npz') as archive:motion={k:archive[k] for k in archive.files}
rng=np.random.default_rng(414+int(variant))
s=bpy.context.scene;bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=64;s.cycles.adaptive_threshold=.018;s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.max_bounces=6;s.render.use_persistent_data=True;s.render.threads_mode='FIXED';s.render.threads=3
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=97;s.render.fps=30;s.frame_end=300;s.view_settings.view_transform='AgX';s.render.use_motion_blur=True;s.render.motion_blur_shutter=.30
s.world.use_nodes=True;s.world.node_tree.nodes.get('Background').inputs[0].default_value=(0,0,0,1);s.world.node_tree.nodes.get('Background').inputs[1].default_value=0
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'
if '--cpu' in args:
 s.cycles.device='CPU';s.cycles.samples=24;s.cycles.denoiser='OPENIMAGEDENOISE';s.cycles.denoising_use_gpu=False;s.render.resolution_x=1280;s.render.resolution_y=720
def mat(name,col,rough):
 m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF');p.inputs['Base Color'].default_value=(*col,1);p.inputs['Roughness'].default_value=rough
 noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=65;noise.inputs['Detail'].default_value=3
 bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.55;bump.inputs['Distance'].default_value=.028;l.new(noise.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],p.inputs['Normal'])
 info=n.new('ShaderNodeObjectInfo');mix=n.new('ShaderNodeMixRGB');mix.blend_type='MIX';mix.inputs[1].default_value=(*[c*.58 for c in col],1);mix.inputs[2].default_value=(*[c*1.3 for c in col],1);l.new(info.outputs['Random'],mix.inputs[0]);l.new(mix.outputs[0],p.inputs['Base Color']);return m
stone=mat('Layered mineral surface',(.065,.043,.024),.81);fracture=mat('Fresh fracture',(.11,.084,.054),.89)
births=[];bodies=[]
for k,center in enumerate(d['centers']):
 v=d['verts'][d['offsets'][k]:d['offsets'][k+1]].copy();f=d['faces'][d['faceOffsets'][k]:d['faceOffsets'][k+1]]
 v[:,1]*=1.7
 wx=v[:,0]+center[0];wz=v[:,2]+center[2]
 v[:,1]+=.055*np.sin(wx*8+wz*3)*np.sin(wz*10-wx*2)+.020*np.sin(wx*27-wz*21)*np.cos(wz*17+wx*13)
 center=center.copy();center[1]+=rng.uniform(-.095,.095)
 me=bpy.data.meshes.new(f'Closed fragment {k}');me.from_pydata(v.tolist(),[],f.tolist());me.materials.append(stone);me.materials.append(fracture);me.update()
 for poly in me.polygons:poly.material_index=0 if abs(poly.normal.y)>.7 else 1;poly.use_smooth=abs(poly.normal.y)>.85
 o=bpy.data.objects.new(f'Stone {k:03}',me);bpy.context.collection.objects.link(o);bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.rigidbody.object_add();o.select_set(False)
 rb=o.rigid_body;rb.mass=max(.1,float(d['volume'][k])*2300*1.7);rb.collision_shape='CONVEX_HULL';rb.use_margin=True;rb.collision_margin=.0015;rb.friction=.8;rb.restitution=.06;rb.linear_damping=.12;rb.angular_damping=.2
 born=float(d['birth'][k]);bf=max(1,round(born*30));rb.kinematic=True;o.keyframe_insert('rigid_body.kinematic',frame=1);o.keyframe_insert('rigid_body.kinematic',frame=187);rb.kinematic=False;o.keyframe_insert('rigid_body.kinematic',frame=188)
 o.hide_render=True;o.keyframe_insert('hide_render',frame=1);o.keyframe_insert('hide_render',frame=max(1,bf-1));o.hide_render=False;o.keyframe_insert('hide_render',frame=bf)
 nozzle=np.array([np.interp(born,motion['times'],motion['points'][:,0]),-.20,np.interp(born,motion['times'],motion['points'][:,1])]);offset=nozzle-center+np.array([-.25,0,-.10]);tilt=rng.normal(0,.22,3)
 # Expand neighboring fragments gently before free release, avoiding the
 # interpenetration caused by unrelated lateral launch velocities.
 impulse=np.array([center[0]*.10,np.sign(center[1])*.5,(center[2]-2.95)*.10])+rng.normal(0,[.012,.05,.012]);spin=rng.normal(0,.12,3)
 for frame in sorted(set([1,bf,*range(bf,min(185,bf+34)),185,186,187])):
  age=max(0,frame/30-born);factor=(1+18*age)*math.exp(-18*age);pos=center+offset*factor;rot=tilt*math.exp(-10*age)
  if frame>=186:pos=center+impulse*(frame-185)/30;rot=spin*(frame-185)/30
  o.location=pos;o.rotation_euler=rot;o.keyframe_insert('location',frame=frame);o.keyframe_insert('rotation_euler',frame=frame)
 for fc in o.animation_data.action.fcurves:
  for key in fc.keyframe_points:key.interpolation='CONSTANT' if fc.data_path in ['hide_render','rigid_body.kinematic'] else 'LINEAR'
 births.append(dict(frame=bf,center=center.tolist(),mass=rb.mass,releaseVelocity=impulse.tolist()));bodies.append(o)
s.rigidbody_world.substeps_per_frame=8;s.rigidbody_world.solver_iterations=20;s.rigidbody_world.point_cache.frame_start=1;s.rigidbody_world.point_cache.frame_end=300;s.gravity=(0,0,-9.81)
bpy.ops.mesh.primitive_plane_add(size=100,location=(0,0,-4));floor=bpy.context.object;floor.hide_render=True;bpy.ops.rigidbody.object_add();floor.rigid_body.type='PASSIVE'
for name,loc,power,size in [('Key',(-4,-2,6.5),1050,2.0),('Fill',(4,-3,2),90,4.0),('Rim',(3,2,5),1000,3.0)]:
 light=bpy.data.lights.new(name,'AREA');light.energy=power;light.shape='DISK';light.size=size;o=bpy.data.objects.new(name,light);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,2.95))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-18,3.10));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,2.95))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';s.camera=cam
started=time.time();transforms=[]
for f in range(300):
 s.frame_set(f+1);t=f/30;q=max(0,min(1,(t-2.4)));q=q*q*(3-2*q);cam.data.ortho_scale=11.4*(.926+.074*q)
 if pilot and f not in [60,120,180,210]:continue
 s.render.filepath=str(out/f'{f:04}.jpg');bpy.ops.render.render(write_still=True)
 transforms.append([list(o.matrix_world.translation) for o in bodies])
 if f%15==0:print('FRAME',f,'seconds',round(time.time()-started,1),flush=True)
 if f==120 and '--ungated' not in args and not pilot:
  print('REVIEW GATE earth '+variant,flush=True)
  while not (B/f'continue-earth-{variant}').exists():time.sleep(.5)
np.savez_compressed(O/('pilot-transforms.npz' if pilot else 'transforms.npz'),positions=np.array(transforms,dtype='f'))
(O/('pilot-report.json' if pilot else 'report.json')).write_text(json.dumps(dict(variant=variant,frames=4 if pilot else 300,bodies=len(bodies),births=births,method='Critically damped assembly guide, held pose, physical Bullet contacts and gravity after release; immutable closed fragment meshes',seconds=time.time()-started),indent=2),encoding='utf-8')
print('COMPLETE',flush=True)
