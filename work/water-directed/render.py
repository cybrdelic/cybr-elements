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
water=material('Clear water',(1,1,1),.025,1)
a=water.node_tree.nodes.new('ShaderNodeVolumeAbsorption');a.inputs['Color'].default_value=(.65,.88,.92,1);a.inputs['Density'].default_value=.65;water.node_tree.links.new(a.outputs[0],water.node_tree.nodes.get('Material Output').inputs['Volume'])
foam=material('Sparse spray',(.85,.9,.92),.08,1)
fn=foam.node_tree.nodes;fl=foam.node_tree.links;attr=fn.new('ShaderNodeAttribute');attr.attribute_name='spray_alpha';mix=fn.new('ShaderNodeMixShader');transparent=fn.new('ShaderNodeBsdfTransparent');fl.new(attr.outputs['Fac'],mix.inputs[0]);fl.new(transparent.outputs[0],mix.inputs[1]);fl.new(fn.get('Principled BSDF').outputs[0],mix.inputs[2]);fl.new(mix.outputs[0],fn.get('Material Output').inputs['Surface'])
stage=material('Continuous studio backdrop',(.18,.21,.23),.45)
n=stage.node_tree.nodes;links=stage.node_tree.links;noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=.28;noise.inputs['Detail'].default_value=0
tex=n.new('ShaderNodeNewGeometry');links.new(tex.outputs['Position'],noise.inputs['Vector']);ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.022,.035,.042,1);ramp.color_ramp.elements[1].color=(.08,.105,.12,1);links.new(noise.outputs['Fac'],ramp.inputs[0]);links.new(ramp.outputs[0],n.get('Principled BSDF').inputs['Base Color'])
profile=[(-18,.03),(2,.03)]+[(2+1.6*np.sin(t),.03+1.6*(1-np.cos(t))) for t in np.linspace(0,np.pi/2,32)[1:]]+[(3.6,12)]
v=[(x,y,z) for x in [-30,30] for y,z in profile];l=len(profile);f=[(i,i+1,l+i+1,l+i) for i in range(l-1)];m=bpy.data.meshes.new('Cyclorama');m.from_pydata(v,[],f);o=bpy.data.objects.new('Cyclorama',m);s.collection.objects.link(o);m.materials.append(stage)
for p in m.polygons:p.use_smooth=True
s.world.use_nodes=True;s.world.node_tree.nodes.get('Background').inputs[0].default_value=(.22,.25,.28,1);s.world.node_tree.nodes.get('Background').inputs[1].default_value=.28
for name,loc,power,col,width,height in [('Window',(-2,-1,5),600,(1,.97,.92),4,1.4),('Edge',(5,2,4),400,(.84,.94,1),3,.65),('Soft front',(2,-4,3),120,(1,1,1),3,3)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.color=col;d.shape='RECTANGLE';d.size=width;d.size_y=height;o=bpy.data.objects.new(name,d);s.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((2.34,.6,1.7))-o.location).to_track_quat('-Z','Y').to_euler()
card=material('Black reflection flag',(.003,.004,.005),.75)
for x in [-2.6,6.6]:
 bpy.ops.mesh.primitive_plane_add(size=1,location=(x,-.6,2.6));o=bpy.context.object;o.scale=(2.2,4.5,1);o.rotation_euler=(Vector((2.34,.6,1.7))-o.location).to_track_quat('Z','Y').to_euler();o.data.materials.append(card)
bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.lens=52;s.camera=cam
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1);base=bpy.context.object;iv=np.array([v.co[:] for v in base.data.vertices]);iff=np.array([p.vertices[:] for p in base.data.polygons]);bpy.data.objects.remove(base,do_unlink=True)
def mesh(name,v,f,mat):
 m=bpy.data.meshes.new(name);m.from_pydata(v.tolist(),[],f.tolist());m.update();o=bpy.data.objects.new(name,m);s.collection.objects.link(o);m.materials.append(mat)
 for p in m.polygons:p.use_smooth=True
 return o
def spheres(name,pos,r,mat,opacity=None):
 if not len(pos):return None
 v=(pos[:,None,:]+iv[None,:,:]*r[:,None,None]).reshape(-1,3);f=(iff[None,:,:]+np.arange(len(pos))[:,None,None]*len(iv)).reshape(-1,3);obj=mesh(name,v,f,mat)
 if opacity is not None:
  attr=obj.data.attributes.new('spray_alpha','FLOAT','POINT');attr.data.foreach_set('value',np.repeat(opacity,len(iv)).astype('float32'))
 return obj
def coords(p):return p[:,[0,2,1]]
frames=[int(x) for x in sys.argv[sys.argv.index('--frames')+1].split(',')] if '--frames' in sys.argv else range(240)
out=ROOT/('proof-final' if '--no-spray' in sys.argv else 'frames');out.mkdir(exist_ok=True);start=time.time()
for f in frames:
 path=ROOT/f'meshes-final/{f:04}.npz'
 while not path.exists():time.sleep(1)
 t=f/96;u=np.clip((t-.08)/.67,0,1);u=u*u*(3-2*u);exit=np.clip((t-1.3)/1.0,0,1);cx=1.2+(2.34-1.2)*u+.24*exit;cam.location=(cx,-4.1-2.3*u,2.15+.30*u);cam.rotation_euler=(Vector((cx,.60,1.70))-cam.location).to_track_quat('-Z','Y').to_euler()
 d=np.load(path);obs=[mesh('Fluid',coords(d['verts']),d['faces'][:,[0,2,1]],water)]
 if '--no-spray' not in sys.argv:
  obs.append(spheres('Primary drops',coords(d['drops']),d['radii'],water));w=d['white'];obs.append(spheres('Secondary spray',coords(w[:,:3]),w[:,3],foam,w[:,5]))
 s.render.filepath=str(out/f'{f:04}.png');bpy.ops.render.render(write_still=True)
 for o in obs:
  if o:m=o.data;bpy.data.objects.remove(o,do_unlink=True);bpy.data.meshes.remove(m)
 print('RENDER',f,round(time.time()-start,1),flush=True)
