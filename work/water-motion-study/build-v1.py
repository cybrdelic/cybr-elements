"""Motion study: actual Mantaflow FLIP liquid from a moving emitter. No letter mesh."""
import bpy, numpy as np, math, json, time
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.frame_start=1;s.frame_end=144;s.render.fps=24
s.gravity=(0,0,-9.81);s.render.threads_mode='FIXED';s.render.threads=8
def cube(name,loc,scale):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.scale=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return o
domain=cube('Free liquid domain',(0,0,1.8),(11,3.2,7))
mod=domain.modifiers.new('Mantaflow liquid','FLUID');mod.fluid_type='DOMAIN';ds=mod.domain_settings;ds.domain_type='LIQUID'
ds.resolution_max=192;ds.cache_type='ALL';ds.cache_directory=str(ROOT/'cache');ds.cache_frame_start=1;ds.cache_frame_end=144
ds.simulation_method='FLIP';ds.time_scale=.18;ds.use_mesh=True;ds.mesh_scale=2;ds.mesh_smoothen_pos=2;ds.mesh_smoothen_neg=2
ds.timesteps_min=2;ds.timesteps_max=12;ds.cfl_condition=2;ds.surface_tension=.35
if hasattr(ds,'flip_ratio'):ds.flip_ratio=.96
water=bpy.data.materials.new('Clear moving water');water.use_nodes=True;n=water.node_tree.nodes;p=n.get('Principled BSDF');p.inputs['Base Color'].default_value=(.88,.97,1,1);p.inputs['Roughness'].default_value=.035;p.inputs['IOR'].default_value=1.333;p.inputs['Transmission Weight'].default_value=1
a=n.new('ShaderNodeVolumeAbsorption');a.inputs['Color'].default_value=(.25,.68,.82,1);a.inputs['Density'].default_value=.3;water.node_tree.links.new(a.outputs[0],n.get('Material Output').inputs['Volume']);domain.data.materials.append(water)
for p in domain.data.polygons:p.use_smooth=True
bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16,radius=.135);nozzle=bpy.context.object;nozzle.name='Moving water source';nozzle.hide_render=True
fm=nozzle.modifiers.new('Liquid inflow','FLUID');fm.fluid_type='FLOW';fs=fm.flow_settings;fs.flow_type='LIQUID';fs.flow_behavior='INFLOW';fs.use_initial_velocity=True;fs.velocity_factor=.08;fs.subframes=4
motion=np.load(ROOT.parent/'brand-fire-01.npz');times=motion['times'];points=motion['points']
for frame in range(1,145):
 t=(frame-1)/24;u=np.clip((t-.25)/3.35,0,1);pt=u*12.8
 x=float(np.interp(pt,times,points[:,0]));z=float(np.interp(pt,times,points[:,1]));depth=.24*math.sin(u*math.pi*3)+.13*math.sin(u*math.pi*7)
 nozzle.location=(x,depth,z+.35);nozzle.keyframe_insert('location',frame=frame)
 q=np.array([np.interp(min(12.8,pt+.025),times,points[:,0])-x,0,np.interp(min(12.8,pt+.025),times,points[:,1])-z]);q/=max(.0001,np.linalg.norm(q));fs.velocity_coord=tuple(q*.45+np.array([0,.10,.18]));fs.keyframe_insert('velocity_coord',frame=frame)
 fs.use_inflow=.25<=t<=3.6;fs.keyframe_insert('use_inflow',frame=frame)
ground=cube('Wet stone stage',(0,0,-1.42),(16,10,.2));ef=ground.modifiers.new('Liquid collision','FLUID');ef.fluid_type='EFFECTOR'
mat=bpy.data.materials.new('Dark wet stone');mat.use_nodes=True;p=mat.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.018,.033,.045,1);p.inputs['Roughness'].default_value=.27;ground.data.materials.append(mat)
world=bpy.data.worlds.new('Soft dark environment');world.use_nodes=True;s.world=world;world.node_tree.nodes.get('Background').inputs[0].default_value=(.09,.13,.17,1);world.node_tree.nodes.get('Background').inputs[1].default_value=.3
def light(name,loc,power,color,w,h):
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.color=color;d.shape='RECTANGLE';d.size=w;d.size_y=h;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1))-o.location).to_track_quat('-Z','Y').to_euler()
light('Broad soft key',(-3,-4,7),1600,(.8,.9,1),7,5);light('Liquid backlight',(1,2,5),1400,(.38,.7,1),6,4);light('Left edge',(-5,0,2),500,(.75,.88,1),3,3)
bpy.ops.object.camera_add();cam=bpy.context.object;s.camera=cam;cam.data.lens=42
for frame,loc in [(1,(.8,-13,4.6)),(144,(1.4,-14.5,4.9))]:
 cam.location=loc;cam.rotation_euler=(Vector((0,0,1.45))-cam.location).to_track_quat('-Z','Y').to_euler();cam.keyframe_insert('location',frame=frame);cam.keyframe_insert('rotation_euler',frame=frame)
s.render.engine='CYCLES';s.cycles.samples=48;s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.denoising_use_gpu=True;s.cycles.device='GPU';s.cycles.max_bounces=10;s.cycles.transmission_bounces=8;s.render.use_persistent_data=True
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for dev in prefs.devices:dev.use=dev.type=='OPTIX'
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.view_settings.view_transform='AgX'
s.frame_set(1);bpy.ops.object.select_all(action='DESELECT');domain.select_set(True);bpy.context.view_layer.objects.active=domain
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'motion-study.blend'))
start=time.monotonic();bpy.ops.fluid.bake_all();elapsed=time.monotonic()-start
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'motion-study.blend'))
(ROOT/'bake-report.json').write_text(json.dumps({'solver':'Mantaflow FLIP','resolution':192,'frames':144,'slowMotionTimeScale':.18,'seconds':elapsed,'baked':ds.has_cache_baked_data,'meshBaked':ds.has_cache_baked_mesh},indent=2))
print('BAKE_COMPLETE',elapsed,flush=True)
