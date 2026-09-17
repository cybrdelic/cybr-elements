import bpy,sys,json,ast,time
import numpy as np
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parent;O=R/'sigil-02-elements';out=O/'earth-frames-v3';out.mkdir(exist_ok=True)
data=np.load(O/'earth-motion-v3.npz');poses=data['transforms'];radii=data['radii'];birth=data['births']
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=64;s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.adaptive_threshold=.018;s.cycles.max_bounces=6;s.render.use_persistent_data=True;s.render.threads_mode='FIXED';s.render.threads=3;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=96;s.render.fps=30;s.view_settings.view_transform='AgX'
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
if '--cpu-pilot' in sys.argv:
 s.cycles.device='CPU';s.cycles.denoiser='OPENIMAGEDENOISE';s.render.resolution_x=1280;s.render.resolution_y=720;out=O/'earth-pilot-v3';out.mkdir(exist_ok=True)
s.world.use_nodes=True;s.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=0
original=(R/'bending-earth-v5.py').read_text();tree=ast.parse(original);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='material');exec(ast.get_source_segment(original,fn))
mats=[material('Slate interior',(.055,.038,.022)),material('Fresh fracture',(.085,.064,.038)),material('Weathered seams',(.018,.012,.007)),material('Mineral inclusion',(.10,.085,.057))]
layers=json.loads((R/'layered-rocks-clean.json').read_text());meshes=[]
for k,q in enumerate(layers):
 me=bpy.data.meshes.new('Layered fracture '+str(k));me.from_pydata(q['verts'],[],q['faces']);me.update()
 for mat in mats:me.materials.append(mat)
 for face,i in zip(me.polygons,q['materials']):face.material_index=int(i);face.use_smooth=int(i) not in [1,2]
 meshes.append(me)
rocks=[]
for k,r in enumerate(radii):
 o=bpy.data.objects.new('Clast '+str(k),meshes[k%len(meshes)]);bpy.context.collection.objects.link(o);o.scale=(r,r*.9,r);o.rotation_mode='QUATERNION';rocks.append(o)
for name,loc,power,size in [('Key',(-2,-4,3.8),650,2.1),('Rim',(1,2,4),850,3),('Fill',(2,-4,1.2),145,4)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-17,1.95));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1.95))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=10.5;s.camera=cam
frames=[135] if '--cpu-pilot' in sys.argv else [60,135,180,235] if '--pilot' in sys.argv else range(294);started=time.time()
for f in frames:
 if (out/f'{f:04}.jpg').exists():continue
 for k,o in enumerate(rocks):
  o.hide_render=f/30<birth[k] or poses[f,k,2]<-3;o.location=poses[f,k,:3];q=poses[f,k,3:];o.rotation_quaternion=(q[3],q[0],q[1],q[2])
 s.render.filepath=str(out/f'{f:04}.jpg');bpy.ops.render.render(write_still=True)
 print('FRAME',f,'seconds',round(time.time()-started,1),flush=True)
print('EARTH COMPLETE',flush=True)
