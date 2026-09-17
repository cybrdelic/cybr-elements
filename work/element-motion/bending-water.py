import bpy,json,gzip,struct,sys,time
from pathlib import Path
import numpy as np
from mathutils import Vector
R=Path(__file__).resolve().parent;O=R.parent.parent/'outputs/cybrdelic-type/elements/motion';cache=O/'water/cache/material';manifest=json.loads((cache/'manifest.json').read_text());out=R/'bending-rebuild/water-frames';out.mkdir(exist_ok=True)
s=bpy.context.scene;bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=48;s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.adaptive_threshold=.025;s.cycles.max_bounces=12;s.cycles.transmission_bounces=10;s.cycles.glossy_bounces=6;s.cycles.diffuse_bounces=2;s.cycles.caustics_reflective=False;s.cycles.caustics_refractive=False;s.render.use_persistent_data=True;s.render.threads_mode='FIXED';s.render.threads=3;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=96;s.view_settings.view_transform='AgX'
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
# Black camera plate with a studio environment available to reflection and transmission rays.
w=s.world;w.use_nodes=True;n=w.node_tree.nodes;n.clear();l=w.node_tree.links;world=n.new('ShaderNodeOutputWorld');mix=n.new('ShaderNodeMixShader');ray=n.new('ShaderNodeLightPath');env=n.new('ShaderNodeBackground');env.inputs['Color'].default_value=(.24,.36,.43,1);env.inputs['Strength'].default_value=.5;black=n.new('ShaderNodeBackground');black.inputs['Color'].default_value=(0,0,0,1);l.new(ray.outputs['Is Camera Ray'],mix.inputs[0]);l.new(env.outputs[0],mix.inputs[1]);l.new(black.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],world.inputs[0])
tc=n.new('ShaderNodeTexCoord');dot=n.new('ShaderNodeVectorMath');dot.operation='DOT_PRODUCT';dot.inputs[1].default_value=(.55,.15,.80);l.new(tc.outputs['Normal'],dot.inputs[0]);mapping=n.new('ShaderNodeMapRange');mapping.inputs['From Min'].default_value=-1;mapping.inputs['From Max'].default_value=1;l.new(dot.outputs['Value'],mapping.inputs['Value']);ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1]);stops=[(0,(.015,.02,.025)),(.28,(.025,.03,.035)),(.44,(.18,.30,.36)),(.53,(.012,.018,.022)),(.70,(.16,.23,.27)),(.86,(.10,.12,.14)),(1,(.02,.025,.03))]
for i,(pos,color) in enumerate(stops):
 el=ramp.color_ramp.elements[0] if i==0 else ramp.color_ramp.elements.new(pos);el.position=pos;el.color=(*color,1)
l.new(mapping.outputs['Result'],ramp.inputs[0]);l.new(ramp.outputs['Color'],env.inputs['Color']);env.inputs['Strength'].default_value=.8
m=bpy.data.materials.new('Clear water / optical transport');m.use_nodes=True;n=m.node_tree.nodes;p=n.get('Principled BSDF');p.inputs['Base Color'].default_value=(.97,.99,1,1);p.inputs['Roughness'].default_value=.006;p.inputs['IOR'].default_value=1.333;p.inputs['Transmission Weight'].default_value=1;absorb=n.new('ShaderNodeVolumeAbsorption');absorb.inputs['Color'].default_value=(.42,.79,.89,1);absorb.inputs['Density'].default_value=.45;m.node_tree.links.new(absorb.outputs[0],n.get('Material Output').inputs['Volume'])
for name,loc,power,size,sy in [('Long reflection',(-1,-3,4.8),1200,6,1.5),('Vertical reflection',(3,1,2.5),900,1.1,5),('Rim',(-3,2,3),850,3,2)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='RECTANGLE';d.size=size;d.size_y=sy;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-15,1.903125));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1.903125))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=10.5;s.camera=cam
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1);temp=bpy.context.object;iv=np.array([list(v.co) for v in temp.data.vertices]);ifa=np.array([list(p.vertices) for p in temp.data.polygons]);bpy.data.objects.remove(temp,do_unlink=True)
def coords(p):return np.column_stack((p[:,0]/.4-5.25,(p[:,2]-.9)/.4,p[:,1]/.4))
obj=None;start=time.time();args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [];frames=range(120) if '--full' in args else [20,50,80]
for f in frames:
 if '--full' in args and (out/f'{f:04}.jpg').exists():continue
 if obj:
  me=obj.data;bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(me)
 raw=gzip.decompress((cache/f'{f:04}.mesh.gz').read_bytes());nv,nf,nd=struct.unpack_from('<III',raw,4);extent=np.array(manifest['config']['extent']);off=32;verts=np.frombuffer(raw,'<u2',nv*3,off).reshape(-1,3)/65535*extent;off+=nv*6;off+=nv*6+nv;faces=np.frombuffer(raw,'<u4',nf*3,off).reshape(-1,3);off+=nf*12;drops=np.frombuffer(raw,'<u2',nd*3,off).reshape(-1,3)/65535*extent;off+=nd*6;radii=np.frombuffer(raw,'<f4',nd,off)
 verts=coords(verts);faces=faces[:,[0,2,1]];droppos=coords(drops)
 if nd:
  dv=(iv[None]*radii[:,None,None]/.4+droppos[:,None]).reshape(-1,3);df=(ifa[None]+np.arange(nd)[:,None,None]*len(iv)+nv).reshape(-1,3);verts=np.concatenate((verts,dv));faces=np.concatenate((faces,df))
 me=bpy.data.meshes.new('Native FLIP surface');me.from_pydata(verts.tolist(),[],faces.tolist());me.update();obj=bpy.data.objects.new('Water',me);bpy.context.collection.objects.link(obj);me.materials.append(m)
 for p in me.polygons:p.use_smooth=True
 s.render.filepath=str(out/f'{f:04}.jpg');bpy.ops.render.render(write_still=True);print('FRAME',f,round(time.time()-start,1),flush=True)
print('COMPLETE',flush=True)
