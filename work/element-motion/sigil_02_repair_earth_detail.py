import bpy,json,math,random,time,sys
import numpy as np
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from shared_motion import pose,DATA,turn_rate
random.seed(6271);data=json.loads((R/'earth-geometry.json').read_text());out=R/('sigil-02-repair/earth-frames' if '--full' in sys.argv else 'sigil-02-repair/earth-pilot-scanned');out.mkdir(exist_ok=True)
s=bpy.context.scene;bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);s.render.engine='CYCLES';s.cycles.device='GPU' if '--full' in sys.argv else 'CPU';s.cycles.samples=72 if '--full' in sys.argv else 24;s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.adaptive_threshold=.02;s.cycles.max_bounces=6;s.render.use_persistent_data=True;s.render.threads_mode='FIXED';s.render.threads=3;s.render.resolution_x=1920 if '--full' in sys.argv else 1280;s.render.resolution_y=1080 if '--full' in sys.argv else 720;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=97;s.render.fps=30;s.frame_end=192;s.world.color=(0,0,0);s.world.use_nodes=True;s.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(0,0,0,1);s.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=0;s.view_settings.view_transform='AgX'
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'
# Authored earthbending lift during the shared writing beat; full gravity on release.
s.gravity=(0,0,-.22);s.keyframe_insert('gravity',frame=1);s.keyframe_insert('gravity',frame=106);s.gravity=(0,0,-9.81);s.keyframe_insert('gravity',frame=125)
def material(name,color):
 m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=(*color,1);n.inputs['Roughness'].default_value=.86
 noise=m.node_tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=36;noise.inputs['Detail'].default_value=3;bump=m.node_tree.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.23;bump.inputs['Distance'].default_value=.008;m.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height']);m.node_tree.links.new(bump.outputs['Normal'],n.inputs['Normal']);ramp=m.node_tree.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.22;ramp.color_ramp.elements[0].color=(*[v*.42 for v in color],1);ramp.color_ramp.elements[1].position=.8;ramp.color_ramp.elements[1].color=(*[v*1.35 for v in color],1);m.node_tree.links.new(noise.outputs['Fac'],ramp.inputs[0]);m.node_tree.links.new(ramp.outputs['Color'],n.inputs['Base Color']);
 info=m.node_tree.nodes.new('ShaderNodeObjectInfo');rough=m.node_tree.nodes.new('ShaderNodeMapRange');rough.inputs['To Min'].default_value=.64;rough.inputs['To Max'].default_value=.96;m.node_tree.links.new(info.outputs['Random'],rough.inputs['Value']);m.node_tree.links.new(rough.outputs['Result'],n.inputs['Roughness']);
 coarse=m.node_tree.nodes.new('ShaderNodeTexNoise');coarse.inputs['Scale'].default_value=7;coarse.inputs['Detail'].default_value=2;macro=m.node_tree.nodes.new('ShaderNodeBump');macro.inputs['Strength'].default_value=.14;macro.inputs['Distance'].default_value=.016;m.node_tree.links.new(coarse.outputs['Fac'],macro.inputs['Height']);m.node_tree.links.new(bump.outputs['Normal'],macro.inputs['Normal']);m.node_tree.links.new(macro.outputs['Normal'],n.inputs['Normal']);return m
mats=[material('Stone '+str(i),(.09+i*.010,.060+i*.008,.032+i*.006)) for i in range(5)];floorMat=material('Ground',(.008,.009,.010))
bpy.ops.mesh.primitive_plane_add(size=100);floor=bpy.context.object;floor.data.materials.append(floorMat);bpy.ops.rigidbody.object_add();floor.rigid_body.type='PASSIVE';floor.rigid_body.friction=.85;floor.location.z=-5;floor.hide_render=True;floor.select_set(False)
layers=json.loads((R/'layered-rocks-clean.json').read_text());layerMeshes={}
rockMats=[material('Basalt interior',(.048,.042,.033)),material('Fresh fracture',(.090,.082,.064)),material('Weathered seams',(.010,.009,.007)),material('Mineral inclusion',(.14,.12,.083))]
invisible=bpy.data.materials.new('Invisible collision hull');invisible.use_nodes=True;nt=invisible.node_tree;nt.nodes.clear();tr=nt.nodes.new('ShaderNodeBsdfTransparent');mo=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(tr.outputs[0],mo.inputs['Surface'])
# CC0 photogrammetry from Poly Haven; preserve native UV material maps.
scanMeshes=[]
for asset in ['boulder_01','rock_07','rock_09']:
 before=set(bpy.data.objects)
 bpy.ops.import_scene.gltf(filepath=str(R/'sigil-02-repair/scans'/asset/f'{asset}_2k.gltf'))
 imported=[o for o in bpy.data.objects if o not in before]
 for item in imported:
  if item.type!='MESH':continue
  mesh=item.data.copy();mesh.transform(item.matrix_world)
  center=sum((v.co for v in mesh.vertices),Vector())/len(mesh.vertices)
  radius=max((v.co-center).length for v in mesh.vertices)
  for v in mesh.vertices:v.co=(v.co-center)/radius
  mesh.update();scanMeshes.append(mesh)
 for item in imported:bpy.data.objects.remove(item,do_unlink=True)
assert len(scanMeshes)>=3

births=[];spawned=[]
source_rows=json.loads((R/'sigil-02-repair/earth-source.json').read_text())
for k,row in enumerate(source_rows):
 b=2+int(row['time']*30);t=(b-1)/30;center=Vector(row['center']);vel=Vector(row['velocity']);r=row['radius'];p=np.array([center.x,center.z])
 src=data['pieces'][k%len(data['pieces'])];vs=[Vector(v) for v in src['verts']];centroid=sum(vs,Vector())/len(vs);radius=max((v-centroid).length for v in vs);vs=[(v-centroid)*(r/radius) for v in vs]
 me=bpy.data.meshes.new('Convex stone');me.from_pydata(vs,[],src['faces']);me.update();o=bpy.data.objects.new('Emitted stone '+str(k),me);bpy.context.collection.objects.link(o);o.data.materials.append(mats[k%len(mats)]);bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.rigidbody.object_add();o.select_set(False);rb=o.rigid_body;rb.mass=max(.01,src['volume']*(r/radius)**3*2700);rb.collision_shape='CONVEX_HULL';rb.use_margin=True;rb.collision_margin=.001;rb.friction=.68;rb.restitution=.04;rb.linear_damping=.12;rb.angular_damping=.18
 o.location=(50+k*.5,0,-10);o.keyframe_insert('location',frame=1);o.hide_render=True;o.keyframe_insert('hide_render',frame=1);o.keyframe_insert('hide_render',frame=b-2)
 o.location=center-vel/30;o.keyframe_insert('location',frame=b-1);o.hide_render=False;o.keyframe_insert('hide_render',frame=b-1);o.location=center;o.keyframe_insert('location',frame=b)
 o.rotation_euler=[random.random()*6 for _ in range(3)];o.keyframe_insert('rotation_euler',frame=b-1);o.rotation_euler.rotate_axis('Y',random.uniform(-.08,.08));o.keyframe_insert('rotation_euler',frame=b)
 rb.kinematic=True;rb.keyframe_insert('kinematic',frame=1);rb.keyframe_insert('kinematic',frame=b);rb.kinematic=False;rb.keyframe_insert('kinematic',frame=b+1)
 for fc in o.animation_data.action.fcurves:
  for key in fc.keyframe_points:key.interpolation='CONSTANT' if fc.data_path in ['hide_render','rigid_body.kinematic'] else 'LINEAR'
 # Render a layered, eroded surface within the unchanged convex collision hull.
 me.materials.clear();me.materials.append(invisible)
 family=k%len(layers)
 if family not in layerMeshes:
  surface=layers[family];lm=bpy.data.meshes.new('Layered fracture '+str(family));lm.from_pydata(surface['verts'],[],surface['faces']);lm.update()
  for mat in rockMats:lm.materials.append(mat)
  for face,idx in zip(lm.polygons,surface['materials']):face.material_index=int(idx);face.use_smooth=int(idx) not in [1,2]
  layerMeshes[family]=lm
 child=bpy.data.objects.new('Scanned stone '+str(k),scanMeshes[k%len(scanMeshes)] if r>.052 else layerMeshes[family]);bpy.context.collection.objects.link(child);child.parent=o;child.scale=(r,r*.78,r) if k%24==0 else (r,r,r);child.hide_render=True;child.keyframe_insert('hide_render',frame=1);child.keyframe_insert('hide_render',frame=b-2);child.hide_render=False;child.keyframe_insert('hide_render',frame=b-1)
 child.scale.x*=.94+.06*((k*73%101)/100);child.scale.y*=.92+.08*((k*43%97)/96)
 births.append({'frame':b,'source':p.tolist(),'center':list(center),'velocity':list(vel),'radius':r})
s.rigidbody_world.substeps_per_frame=20;s.rigidbody_world.solver_iterations=40;s.rigidbody_world.point_cache.frame_end=192
for name,loc,power,size in [('Key',(-2,-4,3.8),650,2.1),('Rim',(1,2,4),850,3),('Fill',(2,-4,1.2),145,4)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-15,DATA['camera']['center'][1]));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,DATA['camera']['center'][1]))-cam.location).to_track_quat('-Z','Y').to_euler();cam.location=(.65,-13.,3.05);cam.rotation_euler=(Vector((0,0,1.8))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='PERSP';cam.data.lens=44;s.camera=cam
# Secondary fine grit inherits source momentum; gravity, drag, and floor contacts are integrated.
rng=np.random.default_rng(701);count=len(births)*9;gb=np.repeat([q['frame'] for q in births],9);gp=np.repeat([q['center'] for q in births],9,axis=0).astype(float);gv=np.repeat([q['velocity'] for q in births],9,axis=0).astype(float)
gr=np.minimum(.016,.0035/(np.maximum(.015,rng.random(count))**.48));gp+=rng.normal(0,.025,(count,3));gv+=rng.normal(0,.24,(count,3));active=np.zeros(count,dtype=bool)
base=np.array([[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]],dtype=float);gf=np.array([[0,2,4],[2,1,4],[1,3,4],[3,0,4],[2,0,5],[1,2,5],[3,1,5],[0,3,5]]);rotation=np.linalg.qr(rng.normal(size=(count,3,3)))[0];grainShape=np.einsum('nvi,nij->nvj',base[None]*rng.uniform(.55,1.25,(count,1,3)),rotation);faces=(gf[None]+np.arange(count)[:,None,None]*6).reshape(-1,3).tolist();grit=None
s.render.use_motion_blur=True;s.render.motion_blur_shutter=.4
full='--full' in sys.argv;start=time.time();transforms=[]
for f in range(1,193):
 s.frame_set(f)
 transforms.append([[*o.matrix_world.translation,*o.matrix_world.to_quaternion()] for o in bpy.data.objects if o.name.startswith('Emitted stone ')])
 active|=gb==f
 for sub in range(3):
  dt=1/90;gv[active,2]+=s.gravity.z*dt;gv[active]*=np.exp(-.35*dt);gp[active]+=gv[active]*dt
  hit=active&(gp[:,2]<gr-5);gp[hit,2]=gr[hit]-5;gv[hit,2]=np.abs(gv[hit,2])*.12;gv[hit,:2]*=.68
 if grit:
  mesh=grit.data;bpy.data.objects.remove(grit,do_unlink=True);bpy.data.meshes.remove(mesh)
 verts=(gp[:,None,:]+grainShape*gr[:,None,None]*active[:,None,None]).reshape(-1,3)
 verts.reshape(count,6,3)[~active,:,2]=-20
 mesh=bpy.data.meshes.new('Integrated grit');mesh.from_pydata(verts.tolist(),[],faces);mesh.materials.append(rockMats[0]);grit=bpy.data.objects.new('Fine grit',mesh);bpy.context.collection.objects.link(grit)
 if (full and not (out/f'{f-1:04}.jpg').exists()) or (not full and f in [67]):s.render.filepath=str(out/f'{f-1:04}.jpg');bpy.ops.render.render(write_still=True)
 if f%15==0:print('FRAME',f,'seconds',round(time.time()-start,1),flush=True)
np.savez_compressed(R/'sigil-02-repair/earth-transforms.npz',transforms=np.asarray(transforms,dtype=np.float32))
(R/'sigil-02-repair/earth-report.json').write_text(json.dumps({'births':births,'frames':192,'fps':30,'trail':'Full02 variable-width 3D source','scanAssets':['boulder_01','rock_07','rock_09'],'scanLicense':'CC0 / Poly Haven','lift':'Effective gravity .22 during bending, 9.81 on release after frame106. Bullet convex-hull contacts; no target springs.','camera':DATA['camera']}))
