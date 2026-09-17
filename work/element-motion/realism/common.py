import bpy,math,sys
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parent
P=R.parent
sys.path.insert(0,str(P))
from shared_motion import pose,DATA

def setup(samples=128):
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=samples;s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.adaptive_threshold=.025;s.cycles.max_bounces=20;s.cycles.transmission_bounces=16;s.cycles.transparent_max_bounces=24;s.render.use_persistent_data=True
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
 for d in prefs.devices:d.use=d.type=='OPTIX'
 s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.threads_mode='FIXED';s.render.threads=3;s.render.fps=30;s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast'
 w=s.world;w.use_nodes=True;n=w.node_tree.nodes;n.clear();l=w.node_tree.links;output=n.new('ShaderNodeOutputWorld');mix=n.new('ShaderNodeMixShader');ray=n.new('ShaderNodeLightPath');env=n.new('ShaderNodeBackground');tex=n.new('ShaderNodeTexEnvironment');tex.image=bpy.data.images.load(str(R/'assets/studio_small_08_2k.exr'));tc=n.new('ShaderNodeTexCoord');mp=n.new('ShaderNodeMapping');mp.inputs['Rotation'].default_value[2]=1.2;l.new(tc.outputs['Normal'],mp.inputs[0]);l.new(mp.outputs[0],tex.inputs[0]);l.new(tex.outputs[0],env.inputs[0]);env.inputs['Strength'].default_value=1.5;black=n.new('ShaderNodeBackground');black.inputs['Color'].default_value=(0,0,0,1);l.new(ray.outputs['Is Camera Ray'],mix.inputs[0]);l.new(env.outputs[0],mix.inputs[1]);l.new(black.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],output.inputs[0])
 for name,loc,power,size in [('Soft key',(-2,-4,5),450,4),('Leaf rim',(2,2,4),600,3)]:
  light=bpy.data.lights.new(name,'AREA');light.energy=power;light.shape='DISK';light.size=size;ob=bpy.data.objects.new(name,light);bpy.context.collection.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector((0,0,2))-ob.location).to_track_quat('-Z','Y').to_euler()
 bpy.ops.object.camera_add(location=(0,-15,1.903125));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1.903125))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=10.5;s.camera=cam
 if '--cpu' in sys.argv:
  s.cycles.device='CPU';s.render.threads=2;s.cycles.denoiser='OPENIMAGEDENOISE'
 return s,cam

def curve(name,points,radius,material):
 c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=radius;c.bevel_resolution=4;sp=c.splines.new('POLY');sp.points.add(len(points)-1)
 for i,(p,co) in enumerate(zip(sp.points,points)):p.co=(*co,1);p.radius=1-.8*i/max(1,len(points)-1)
 ob=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(ob);c.materials.append(material);return ob
