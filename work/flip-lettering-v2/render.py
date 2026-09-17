import bpy,numpy as np,sys,time
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=48;s.cycles.use_denoising=True;s.cycles.device='GPU';s.cycles.max_bounces=10;s.cycles.transmission_bounces=8;s.render.use_persistent_data=True
s.cycles.denoiser='OPTIX';s.cycles.denoising_use_gpu=True
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for dev in prefs.devices:dev.use=dev.type=='OPTIX'
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.view_settings.view_transform='AgX'
def material(name,col,rough,trans=0):
 m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*col,1);p.inputs['Roughness'].default_value=rough;p.inputs['Transmission Weight'].default_value=trans;p.inputs['IOR'].default_value=1.333;return m
water=material('Water / reference reconstructed surface',(.92,.98,1),.018,1)
a=water.node_tree.nodes.new('ShaderNodeVolumeAbsorption');a.inputs['Color'].default_value=(.36,.77,.86,1);a.inputs['Density'].default_value=.25;water.node_tree.links.new(a.outputs[0],water.node_tree.nodes.get('Material Output').inputs['Volume'])
foam=material('Entrained spray',(.65,.83,.87),.3)
floor=material('Dark floor',(.012,.02,.026),.32)
bpy.ops.mesh.primitive_plane_add(size=200,location=(2.34,.54,0));bpy.context.object.data.materials.append(floor)
s.world.color=(.02,.02,.02);s.world.use_nodes=True;s.world.node_tree.nodes.get('Background').inputs[0].default_value=(.025,.045,.06,1);s.world.node_tree.nodes.get('Background').inputs[1].default_value=.2
for name,loc,power,col,size in [('Key',(-1,-2,5),1000,(.78,.9,1),4),('Rim',(3,3,4),1300,(.48,.82,1),3),('Strip',(6,0,2.5),550,(1,1,1),2)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.color=col;d.shape='RECTANGLE';d.size=size;d.size_y=size*.35;o=bpy.data.objects.new(name,d);s.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((2.34,.54,1.5))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(2.34,-6.6,3.25));cam=bpy.context.object;cam.rotation_euler=(Vector((2.34,.54,1.55))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=48;s.camera=cam
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1);base=bpy.context.object;iv=np.array([v.co[:] for v in base.data.vertices]);iff=np.array([p.vertices[:] for p in base.data.polygons]);bpy.data.objects.remove(base,do_unlink=True)
def mesh(name,v,f,mat):
 m=bpy.data.meshes.new(name);m.from_pydata(v.tolist(),[],f.tolist());m.update();o=bpy.data.objects.new(name,m);s.collection.objects.link(o);m.materials.append(mat)
 for p in m.polygons:p.use_smooth=True
 return o
def spheres(name,pos,r,mat):
 if not len(pos):return None
 v=(pos[:,None,:]+iv[None,:,:]*r[:,None,None]).reshape(-1,3);f=(iff[None,:,:]+np.arange(len(pos))[:,None,None]*len(iv)).reshape(-1,3);return mesh(name,v,f,mat)
def coords(p):return p[:,[0,2,1]]
frames=[int(sys.argv[sys.argv.index('--frame')+1])] if '--frame' in sys.argv else range(192)
out=ROOT/'frames';out.mkdir(exist_ok=True);start=time.time()
for f in frames:
 path=ROOT/f'meshes/{f:04}.npz'
 while not path.exists():time.sleep(1)
 d=np.load(path);obs=[mesh('Fluid',coords(d['verts']),d['faces'][:,[0,2,1]],water),spheres('Primary drops',coords(d['drops']),d['radii'],water)]
 w=d['white'];obs.append(spheres('Secondary spray',coords(w[:,:3]),w[:,3],foam))
 s.render.filepath=str(out/f'{f:04}.png');bpy.ops.render.render(write_still=True)
 for o in obs:
  if o:m=o.data;bpy.data.objects.remove(o,do_unlink=True);bpy.data.meshes.remove(m)
 print('RENDER',f,round(time.time()-start,1),flush=True)
