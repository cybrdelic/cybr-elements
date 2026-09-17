import bpy,json,math,random,time,sys
import numpy as np
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from shared_motion import pose,DATA,turn_rate
random.seed(6271);data=json.loads((R/'earth-geometry.json').read_text());out=R/'subelements/snow-frames';out.mkdir(parents=True,exist_ok=True)
s=bpy.context.scene;bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=24;s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.render.use_persistent_data=True;
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for dev in prefs.devices:dev.use=dev.type=='OPTIX'
s.render.threads_mode='FIXED';s.render.threads=3;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=94;s.render.fps=30;s.frame_end=120;s.world.color=(0,0,0);s.world.use_nodes=True;s.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(0,0,0,1);s.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=0;s.view_settings.view_transform='AgX'
# Authored earthbending lift during the shared writing beat; full gravity on release.
s.gravity=(0,0,-.5);s.keyframe_insert('gravity',frame=1);s.keyframe_insert('gravity',frame=51);s.gravity=(0,0,-2.1);s.keyframe_insert('gravity',frame=65)
def material(name,color):
 m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=(*color,1);n.inputs['Roughness'].default_value=.86
 noise=m.node_tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=22;noise.inputs['Detail'].default_value=3;bump=m.node_tree.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.28;bump.inputs['Distance'].default_value=.001;m.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height']);m.node_tree.links.new(bump.outputs['Normal'],n.inputs['Normal']);ramp=m.node_tree.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.22;ramp.color_ramp.elements[0].color=(*[v*.45 for v in color],1);ramp.color_ramp.elements[1].position=.8;ramp.color_ramp.elements[1].color=(*[v*1.8 for v in color],1);m.node_tree.links.new(noise.outputs['Fac'],ramp.inputs[0]);m.node_tree.links.new(ramp.outputs['Color'],n.inputs['Base Color']);return m
mats=[material('Stone '+str(i),(.09+i*.010,.060+i*.008,.032+i*.006)) for i in range(5)];floorMat=material('Ground',(.008,.009,.010))
bpy.ops.mesh.primitive_plane_add(size=100);floor=bpy.context.object;floor.data.materials.append(floorMat);bpy.ops.rigidbody.object_add();floor.rigid_body.type='PASSIVE';floor.rigid_body.friction=.85;floor.select_set(False)
layers=[];layerMeshes={}
for src in data['pieces']:
 vs=[Vector(v) for v in src['verts']];c=sum(vs,Vector())/len(vs);rad=max((v-c).length for v in vs);layers.append({'verts':[list((v-c)/rad) for v in vs],'faces':src['faces'],'materials':[0]*len(src['faces'])})
rockMats=[material('Slate interior',(.50,.65,.76)),material('Fresh fracture',(.11,.09,.06)),material('Weathered seams',(.025,.016,.009)),material('Mineral inclusion',(.18,.16,.12))]
invisible=bpy.data.materials.new('Invisible collision hull');invisible.use_nodes=True;nt=invisible.node_tree;nt.nodes.clear();tr=nt.nodes.new('ShaderNodeBsdfTransparent');mo=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(tr.outputs[0],mo.inputs['Surface'])
births=[]
for k in range(660):
 b=4+int(k*47/660);t=(b-1)/30;p,d,on,speed=pose(t);angle=random.random()*math.tau;cross=random.random()**.5*.2;along=random.uniform(-.09,.09);center=[float(p[0]-d[1]*math.cos(angle)*cross+d[0]*along),math.sin(angle)*cross,float(p[1]+d[0]*math.cos(angle)*cross+d[1]*along)];vel=[float(d[0])*1.6,random.uniform(-.14,.14),float(d[1])*1.6];births.append({'frame':b,'center':center,'velocity':vel})
s.rigidbody_world.substeps_per_frame=16;s.rigidbody_world.solver_iterations=40;s.rigidbody_world.point_cache.frame_end=120
for name,loc,power,size in [('Key',(-2,-4,3.8),450,3),('Rim',(1,2,4),650,4)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-15,DATA['camera']['center'][1]));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,DATA['camera']['center'][1]))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=DATA['camera']['width'];s.camera=cam
# Secondary fine grit inherits source momentum; gravity, drag, and floor contacts are integrated.
rng=np.random.default_rng(701);count=len(births)*18;gb=np.repeat([q['frame'] for q in births],18);gp=np.repeat([q['center'] for q in births],18,axis=0).astype(float);gv=np.repeat([q['velocity'] for q in births],18,axis=0).astype(float)
gr=np.minimum(.015,.005/(np.maximum(.015,rng.random(count))**.48));gp+=rng.normal(0,.025,(count,3));gv+=rng.normal(0,.24,(count,3));active=np.zeros(count,dtype=bool)
base=np.array([[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]],dtype=float);gf=np.array([[0,2,4],[2,1,4],[1,3,4],[3,0,4],[2,0,5],[1,2,5],[3,1,5],[0,3,5]]);rotation=np.linalg.qr(rng.normal(size=(count,3,3)))[0];grainShape=np.einsum('nvi,nij->nvj',base[None]*rng.uniform(.55,1.25,(count,1,3)),rotation);faces=(gf[None]+np.arange(count)[:,None,None]*6).reshape(-1,3).tolist();grit=None
full='--full' in sys.argv;start=time.time()
for f in range(1,121):
 s.frame_set(f)
 active|=gb==f
 for sub in range(3):
  dt=1/90;gv[active,2]+=s.gravity.z*dt;gv[active]*=np.exp(-1.4*dt);gp[active]+=gv[active]*dt
  hit=active&(gp[:,2]<gr);gp[hit,2]=gr[hit];gv[hit,2]=np.abs(gv[hit,2])*.12;gv[hit,:2]*=.68
 if grit:
  mesh=grit.data;bpy.data.objects.remove(grit,do_unlink=True);bpy.data.meshes.remove(mesh)
 verts=(gp[:,None,:]+grainShape*gr[:,None,None]*active[:,None,None]).reshape(-1,3)
 verts.reshape(count,6,3)[~active,:,2]=-20
 mesh=bpy.data.meshes.new('Integrated grit');mesh.from_pydata(verts.tolist(),[],faces);mesh.materials.append(rockMats[0]);grit=bpy.data.objects.new('Fine grit',mesh);bpy.context.collection.objects.link(grit)
 if full or f in [21,51,81]:s.render.filepath=str(out/f'{f-1:04}.jpg');bpy.ops.render.render(write_still=True)
 if f==51 and not full:
  cam.data.ortho_scale=4.5;cam.location.x=.8;cam.location.z=1.7;s.render.filepath=str(R/'subelements/snow-close.jpg');bpy.ops.render.render(write_still=True);cam.data.ortho_scale=10.5;cam.location.x=0;cam.location.z=1.903125
 if f%15==0:print('FRAME',f,'seconds',round(time.time()-start,1),flush=True)
(R/'subelements/snow-report.json').write_text(json.dumps({'births':births,'frames':120,'fps':30,'trail':'shared-trail.json','lift':'Effective gravity .5 m/s2 during drawing, ramp to 9.81 after frame 51; Integrated particle drag, gravity and floor impacts; no inter-particle contact solve','camera':DATA['camera']}))
