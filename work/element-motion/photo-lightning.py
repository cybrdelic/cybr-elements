import bpy,math,random,sys,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from shared_motion import pose
out=R/'subelements/photo-lightning-frames';out.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=32;s.render.use_persistent_data=True;s.cycles.use_denoising=True;s.cycles.denoiser="OPTIX";s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=96;s.world.color=(0,0,0);s.world.use_nodes=True;s.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=0;s.view_settings.view_transform='AgX'
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
m=bpy.data.materials.new('Ionized channel');m.use_nodes=True;nd=m.node_tree.nodes;nd.clear();e=nd.new('ShaderNodeEmission');e.inputs['Color'].default_value=(.3,.48,1,1);e.inputs['Strength'].default_value=120;output=nd.new('ShaderNodeOutputMaterial');m.node_tree.links.new(e.outputs[0],output.inputs[0])
bpy.ops.mesh.primitive_plane_add(size=100);floor=bpy.context.object;fm=bpy.data.materials.new('Dark ground');fm.use_nodes=True;fm.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.005,.006,.008,1);fm.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.5;floor.data.materials.append(fm)
bpy.ops.object.camera_add(location=(0,-15,1.903125));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1.903125))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=10.5;s.camera=cam
s.use_nodes=True;cn=s.node_tree.nodes;cn.clear();rl=cn.new('CompositorNodeRLayers');gl=cn.new('CompositorNodeGlare');gl.glare_type='FOG_GLOW';gl.quality='HIGH';gl.threshold=1;gl.size=7;gl.mix=-.7;co=cn.new('CompositorNodeComposite');s.node_tree.links.new(rl.outputs['Image'],gl.inputs[0]);s.node_tree.links.new(gl.outputs[0],co.inputs[0])
objects=[]
def channel(points,r):
 c=bpy.data.curves.new('Discharge','CURVE');c.dimensions='3D';c.resolution_u=1;c.bevel_depth=r;c.bevel_resolution=2;p=c.splines.new('POLY');p.points.add(len(points)-1)
 for i,(pt,q) in enumerate(zip(points,p.points)):q.co=(*pt,1);q.radius=max(.1,1-i/len(points)*.8)
 ob=bpy.data.objects.new('Channel',c);bpy.context.collection.objects.link(ob);c.materials.append(m);objects.append(ob)
def jag(a,b,depth,rng):
 if depth==0:return [a,b]
 mid=(a+b)/2;length=(a-b).length;mid+=Vector((rng.gauss(0,length*.13),rng.gauss(0,length*.1),rng.gauss(0,length*.13)));l=jag(a,mid,depth-1,rng);return l[:-1]+jag(mid,b,depth-1,rng)
for f in (range(120) if '--full' in sys.argv else ([int(sys.argv[sys.argv.index("--frame")+1])] if "--frame" in sys.argv else [40,48])):
 for ob in objects:cu=ob.data;bpy.data.objects.remove(ob,do_unlink=True);bpy.data.curves.remove(cu)
 objects=[];t=f/30;rng=random.Random(901+f//3);end=min(1.6,max(.08,t));start=max(.08,end-.95);base=[]
 if .12<t<2.25:
  for j in range(26):
   p=pose(start+(end-start)*j/25)[0];base.append(Vector((float(p[0]),0,float(p[1]))))
  pts=[]
  for a,b in zip(base[:-1],base[1:]):pts.extend(jag(a,b,2,rng)[:-1])
  pts.append(base[-1]);channel(pts,.004)
  for j in range(8,len(pts)-2,7):
   a=pts[j];direction=(pts[j]-pts[j-3]).normalized();tip=a+direction*rng.uniform(.15,.5)+Vector((rng.uniform(-.4,.4),rng.uniform(-.3,.3),rng.uniform(-.5,.5)));branch=jag(a,tip,4,rng);channel(branch,.0015)
   if j%2:channel(jag(branch[7],branch[7]+Vector((rng.uniform(-.25,.25),.1,rng.uniform(-.3,.3))),3,rng),.0006)
 e.inputs['Strength'].default_value=(100 if f%5<3 else 18)*max(0,1-max(0,t-1.7)/.55)
 s.render.filepath=str(out/f'{f:04}.jpg');bpy.ops.render.render(write_still=True)
