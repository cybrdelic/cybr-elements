import bpy,json,gzip,struct,sys,time
from pathlib import Path
import numpy as np
from mathutils import Vector
R=Path(__file__).resolve().parent;O=R.parent.parent/'outputs/cybrdelic-type/elements/motion';cache=R/'bending-rebuild-v2/water-mesh-smooth';manifest=json.loads((cache/'manifest.json').read_text());out=R/'bending-rebuild-v2/water-smooth-frames';out.mkdir(exist_ok=True)
s=bpy.context.scene;bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=64;s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.adaptive_threshold=.018;s.cycles.max_bounces=12;s.cycles.transmission_bounces=10;s.cycles.glossy_bounces=6;s.cycles.diffuse_bounces=2;s.cycles.caustics_reflective=False;s.cycles.caustics_refractive=False;s.render.use_persistent_data=True;s.render.threads_mode='FIXED';s.render.threads=3;s.render.resolution_x=2560;s.render.resolution_y=1440;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=97;s.view_settings.view_transform='AgX'
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
# A physically black world behind transmission and camera rays.
w=s.world;w.use_nodes=True;w.node_tree.nodes.get('Background').inputs['Color'].default_value=(0,0,0,1);w.node_tree.nodes.get('Background').inputs['Strength'].default_value=0
m=bpy.data.materials.new('Clear water / optical transport');m.use_nodes=True;n=m.node_tree.nodes;p=n.get('Principled BSDF');p.inputs['Base Color'].default_value=(.995,.999,1,1);p.inputs['Roughness'].default_value=.006;p.inputs['IOR'].default_value=1.333;p.inputs['Transmission Weight'].default_value=1;absorb=n.new('ShaderNodeVolumeAbsorption');absorb.inputs['Color'].default_value=(.24,.65,.72,1);absorb.inputs['Density'].default_value=.14;m.node_tree.links.new(absorb.outputs[0],n.get('Material Output').inputs['Volume'])
for name,loc,power,size,sy in [('Long white strip',(-1,-3,4.8),900,5.5,.8),('Edge card',(3,1.4,2.5),1100,1.0,4.5),('Soft rim',(-3,2,3.6),750,3.8,1.7),('Low bounce',(-1,-1,-1.3),240,4,.9),('Broad front card',(1,-4,3.4),1050,4.6,3.2)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.color=(.70,.85,1.0) if name=='Broad front card' else (1,1,1);d.shape='RECTANGLE';d.size=size;d.size_y=sy;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-15,1.903125));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1.903125))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=10.5;s.camera=cam
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1);temp=bpy.context.object;iv=np.array([list(v.co) for v in temp.data.vertices]);ifa=np.array([list(p.vertices) for p in temp.data.polygons]);bpy.data.objects.remove(temp,do_unlink=True)
origin=np.array(manifest['origin']);scale=manifest['spaceScale']
def coords(p):return np.column_stack(((p[:,0]-origin[0])/scale,(p[:,2]-origin[2])/scale,(p[:,1]-origin[1])/scale))
obj=None;start=time.time();args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [];frames=range(120) if '--full' in args else [21,42,45]
for f in frames:
 if '--full' in args and (out/f'{f:04}.jpg').exists():continue
 if obj:
  me=obj.data;bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(me)
 while not (cache/f'{f:04}.mesh.gz').exists():time.sleep(.4)
 raw=gzip.decompress((cache/f'{f:04}.mesh.gz').read_bytes());nv,nf,nd=struct.unpack_from('<III',raw,4);extent=np.array(manifest['config']['extent']);off=32;verts=np.frombuffer(raw,'<u2',nv*3,off).reshape(-1,3)/65535*extent;off+=nv*6;off+=nv*6+nv;faces=np.frombuffer(raw,'<u4',nf*3,off).reshape(-1,3);off+=nf*12;drops=np.frombuffer(raw,'<u2',nd*3,off).reshape(-1,3)/65535*extent;off+=nd*6;radii=np.frombuffer(raw,'<f4',nd,off)
 verts=coords(verts);faces=faces[:,[0,2,1]];droppos=coords(drops)
 if nd:
  dv=(iv[None]*radii[:,None,None]/.4+droppos[:,None]).reshape(-1,3);df=(ifa[None]+np.arange(nd)[:,None,None]*len(iv)+nv).reshape(-1,3);verts=np.concatenate((verts,dv));faces=np.concatenate((faces,df))
 me=bpy.data.meshes.new('Native FLIP surface');me.from_pydata(verts.tolist(),[],faces.tolist());me.update();obj=bpy.data.objects.new('Water',me);bpy.context.collection.objects.link(obj);me.materials.append(m)
 for p in me.polygons:p.use_smooth=True
 s.render.filepath=str(out/f'{f:04}.jpg');bpy.ops.render.render(write_still=True);print('FRAME',f,round(time.time()-start,1),flush=True)
print('COMPLETE',flush=True)
