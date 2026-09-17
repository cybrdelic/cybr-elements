"""Inspect actual Mantaflow mesh caches, never the source letter geometry."""
from pathlib import Path
import bpy,sys,json,time,shutil
import numpy as np
from mathutils import Vector

R=Path(__file__).resolve().parent
sys.path.insert(0,str(R.parent/'dynamics'))
import scene
folder=R/'native-liquid-01-v2'
bpy.ops.wm.open_mainfile(filepath=str(folder/'native-liquid.blend'))
s=bpy.context.scene
domain=bpy.data.objects['Native liquid simulation']
d=domain.modifiers['FLIP liquid'].domain_settings
d.cache_directory=str(folder/'cache')
s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=192
s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.use_adaptive_sampling=True;s.cycles.adaptive_threshold=.009
s.cycles.max_bounces=12;s.cycles.transmission_bounces=10;s.cycles.glossy_bounces=6
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100
s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=97
s.render.use_persistent_data=True
s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast';s.view_settings.exposure=-.35
pref=bpy.context.preferences.addons['cycles'].preferences;pref.compute_device_type='OPTIX';pref.get_devices()
for device in pref.devices:device.use=device.type=='OPTIX'
w=bpy.data.worlds.new('Black stage');w.use_nodes=True;s.world=w
n=w.node_tree.nodes;l=w.node_tree.links
n['Background'].inputs[0].default_value=(0,0,0,1);n['Background'].inputs[1].default_value=0
ray=n.new('ShaderNodeLightPath');env=n.new('ShaderNodeBackground');tex=n.new('ShaderNodeTexEnvironment')
tex.image=bpy.data.images.load(str(scene.ASSETS/'studio_small_08_2k.exr'));env.inputs[1].default_value=.35
mix=n.new('ShaderNodeMixShader');l.new(tex.outputs[0],env.inputs[0]);l.new(ray.outputs['Is Reflection Ray'],mix.inputs[0]);l.new(n['Background'].outputs[0],mix.inputs[1]);l.new(env.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],n['World Output'].inputs[0])
for name,loc,power,width,height in [('Key',(-2,-4,5),1400,5,1.8),('Rim',(2,1.6,3.8),1900,1.4,4),('Low',(-1,-1.5,-.1),500,4,.3)]:
    light=bpy.data.lights.new(name,'AREA');light.energy=power;light.shape='RECTANGLE';light.size=width;light.size_y=height
    ob=bpy.data.objects.new(name,light);bpy.context.collection.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector((0,0,1.9))-ob.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-15,2.2));s.camera=bpy.context.object;s.camera.rotation_euler=(Vector((0,0,2.2))-s.camera.location).to_track_quat('-Z','Y').to_euler();s.camera.data.type='ORTHO';s.camera.data.ortho_scale=10.5
mat=scene.material('Dense liquid',(.032,.00055,.0009),.17,trans=.04,ior=1.36)
p=mat.node_tree.nodes.get('Principled BSDF');p.inputs['Subsurface Weight'].default_value=.10;p.inputs['Subsurface Radius'].default_value=(.008,.0012,.00055)
domain.data.materials.clear();domain.data.materials.append(mat)
smooth=domain.modifiers.new('Smooth liquid normals','NODES');g=bpy.data.node_groups.new('Surface normals','GeometryNodeTree');smooth.node_group=g
g.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');g.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
inp=g.nodes.new('NodeGroupInput');out=g.nodes.new('NodeGroupOutput');shade=g.nodes.new('GeometryNodeSetShadeSmooth');g.links.new(inp.outputs[0],shade.inputs['Geometry']);g.links.new(shade.outputs[0],out.inputs[0])
frames=list(range(1,91)) if '--all' in sys.argv else ([int(x) for x in sys.argv[sys.argv.index('--frames')+1].split(',')] if '--frames' in sys.argv else [20,45,60,72,90])
dest=folder/'frames';dest.mkdir(exist_ok=True);reports=[]
for frame in frames:
    s.frame_set(frame);bpy.context.view_layer.update()
    evaluated=domain.evaluated_get(bpy.context.evaluated_depsgraph_get());me=evaluated.to_mesh();count=len(me.vertices);faces=len(me.polygons)
    if count<20:
        evaluated.to_mesh_clear()
        if frame>2:raise RuntimeError(f'No baked fluid surface at frame {frame}: {count} vertices')
        shutil.copyfile(R.parent/'sigils'/'black-frame.jpg',dest/f'{frame:04}.jpg')
        reports.append({'frame':frame,'vertices':count,'status':'Empty initial liquid frame'})
        continue
    vv=np.empty(count*3,dtype='f4');me.vertices.foreach_set('co',vv);vv=vv.reshape(-1,3)
    report={'frame':frame,'vertices':count,'faces':faces,'boundsLocal':[vv.min(axis=0).tolist(),vv.max(axis=0).tolist()]};evaluated.to_mesh_clear()
    start=time.time();s.render.filepath=str(dest/f'{frame:04}.jpg');bpy.ops.render.render(write_still=True);report['renderSeconds']=time.time()-start;reports.append(report)
    (folder/'render-report.json').write_text(json.dumps(reports,indent=2));print('NATIVE FRAME',frame,count,flush=True)
