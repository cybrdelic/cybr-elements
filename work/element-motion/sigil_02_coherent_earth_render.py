"""Guided fracture assembly, sustained silhouette, then native Bullet release."""
import bpy,json,math,sys,time
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parent;O=R/'sigil-02-coherent';full='--full' in sys.argv
out=O/('earth-frames' if full else 'earth-pilot');out.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.device='GPU' if full else 'CPU';s.cycles.samples=48 if full else 24;s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.max_bounces=6;s.render.use_persistent_data=True;s.render.threads_mode='FIXED';s.render.threads=2
s.render.resolution_x=1920 if full else 1280;s.render.resolution_y=1080 if full else 720;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=97;s.render.fps=30;s.frame_end=300;s.gravity=(0,0,-9.81);s.view_settings.view_transform='AgX'
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
data=json.loads((O/'earth-geometry.json').read_text());objects=[]
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
 arrival=max(12,int(row['birth']*30)+8);birth=max(1,arrival-15);release=175+(k*7%15)
 o.hide_render=True;o.keyframe_insert('hide_render',frame=1);o.keyframe_insert('hide_render',frame=birth-1);o.hide_render=False;o.keyframe_insert('hide_render',frame=birth)
 o.location=center+Vector((-.24,.5+.1*math.sin(k),-.68));o.rotation_euler=(.10*math.sin(k),.08*math.cos(k),.06*math.sin(k*2));o.keyframe_insert('location',frame=birth);o.keyframe_insert('rotation_euler',frame=birth)
 o.location=center+Vector((-.05,.12,-.08));o.rotation_euler=(.025*math.sin(k),.015*math.cos(k),0);o.keyframe_insert('location',frame=arrival-4);o.keyframe_insert('rotation_euler',frame=arrival-4)
 o.location=center;o.rotation_euler=(0,0,0);o.keyframe_insert('location',frame=arrival);o.keyframe_insert('rotation_euler',frame=arrival)
 for f in range(arrival+8,release,8):
  o.location=center+Vector((.0015*math.sin(f*.05+k),.007*math.sin(f*.08+k),.0015*math.cos(f*.06+k)));o.keyframe_insert('location',frame=f)
 o.location=center;o.keyframe_insert('location',frame=release-1);o.keyframe_insert('location',frame=release)
 rb.kinematic=True;rb.keyframe_insert('kinematic',frame=1);rb.keyframe_insert('kinematic',frame=release);rb.kinematic=False;rb.keyframe_insert('kinematic',frame=release+1)
 for fc in o.animation_data.action.fcurves:
  for key in fc.keyframe_points:key.interpolation='CONSTANT' if fc.data_path in ['hide_render','rigid_body.kinematic'] else 'BEZIER'
 objects.append(o)
s.rigidbody_world.substeps_per_frame=8;s.rigidbody_world.solver_iterations=20;s.rigidbody_world.point_cache.frame_end=300
for name,loc,power,size in [('Soft key',(-3,-5,6),950,4),('Warm rim',(3,2,4.8),700,3),('Broad fill',(4,-4,1.5),180,5)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;d.color=(1,.9,.76) if 'Warm' in name else (1,1,1);o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(.65,-16.8,4.2375));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,2.8875))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=44;cam.data.sensor_width=36;s.camera=cam
s.render.use_motion_blur=True;s.render.motion_blur_shutter=.35;start=time.time();rows=[]
for f in range(1,301):
 s.frame_set(f)
 if f%30==0:rows.append(dict(frame=f,finite=all(all(math.isfinite(v) for v in o.matrix_world.translation) for o in objects),minZ=min(o.matrix_world.translation.z for o in objects)))
 if (full or f in [76,166]) and not (out/f'{f-1:04}.jpg').exists():
  s.render.filepath=str(out/f'{f-1:04}.jpg');bpy.ops.render.render(write_still=True)
 if f%30==0:print('EARTH',f,round(time.time()-start,1),flush=True)
(O/('earth-report.json' if full else 'earth-pilot-report.json')).write_text(json.dumps(dict(frames=300,pieces=len(objects),method='Authored rigid assembly and hold, native Bullet collisions and gravity after frame175; photogrammetry stone material',rows=rows),indent=2))
print('EARTH COMPLETE',flush=True)
