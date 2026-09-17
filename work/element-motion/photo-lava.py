import bpy,json,gzip,struct,sys,time
from pathlib import Path
import numpy as np
from mathutils import Vector
KIND=sys.argv[sys.argv.index('--kind')+1] if '--kind' in sys.argv else 'lava'
R=Path(__file__).resolve().parent;O=R.parent.parent/'outputs/cybrdelic-type/elements/motion';cache=O/('water/cache/viscous' if KIND in ['lava','mud'] else 'water/cache/material');manifest=json.loads((cache/'manifest.json').read_text());out=R/'subelements'/f'photo-{KIND}-frames';out.mkdir(parents=True,exist_ok=True)
s=bpy.context.scene;bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=48;s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.adaptive_threshold=.06;s.cycles.max_bounces=12;s.cycles.transmission_bounces=10;s.cycles.glossy_bounces=6;s.cycles.diffuse_bounces=2;s.cycles.caustics_reflective=False;s.cycles.caustics_refractive=False;s.render.use_persistent_data=True;s.render.threads_mode='FIXED';s.render.threads=3;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=96;s.view_settings.view_transform='AgX'
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
# Black camera plate with a studio environment available to reflection and transmission rays.
w=s.world;w.use_nodes=True;n=w.node_tree.nodes;n.clear();l=w.node_tree.links;world=n.new('ShaderNodeOutputWorld');mix=n.new('ShaderNodeMixShader');ray=n.new('ShaderNodeLightPath');env=n.new('ShaderNodeBackground');env.inputs['Color'].default_value=(.24,.36,.43,1);env.inputs['Strength'].default_value=.5;black=n.new('ShaderNodeBackground');black.inputs['Color'].default_value=(0,0,0,1);l.new(ray.outputs['Is Camera Ray'],mix.inputs[0]);l.new(env.outputs[0],mix.inputs[1]);l.new(black.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],world.inputs[0])
tc=n.new('ShaderNodeTexCoord');dot=n.new('ShaderNodeVectorMath');dot.operation='DOT_PRODUCT';dot.inputs[1].default_value=(.55,.15,.80);l.new(tc.outputs['Normal'],dot.inputs[0]);mapping=n.new('ShaderNodeMapRange');mapping.inputs['From Min'].default_value=-1;mapping.inputs['From Max'].default_value=1;l.new(dot.outputs['Value'],mapping.inputs['Value']);ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1]);stops=[(0,(.015,.02,.025)),(.28,(.025,.03,.035)),(.44,(.18,.30,.36)),(.53,(.012,.018,.022)),(.70,(.16,.23,.27)),(.86,(.10,.12,.14)),(1,(.02,.025,.03))]
for i,(pos,color) in enumerate(stops):
 el=ramp.color_ramp.elements[0] if i==0 else ramp.color_ramp.elements.new(pos);el.position=pos;el.color=(*color,1)
l.new(mapping.outputs['Result'],ramp.inputs[0]);l.new(ramp.outputs['Color'],env.inputs['Color']);env.inputs['Strength'].default_value=.8
m=bpy.data.materials.new(KIND);m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF');p.inputs['IOR'].default_value=1.333;p.inputs['Roughness'].default_value=.025
noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=12;noise.inputs['Detail'].default_value=4;noise.inputs['Roughness'].default_value=.72
bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.32;bump.inputs['Distance'].default_value=.035;l.new(noise.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],p.inputs['Normal'])
if KIND=='lava':
 p.inputs['Base Color'].default_value=(.012,.003,.001,1);p.inputs['Roughness'].default_value=.28
 at=n.new('ShaderNodeAttribute');at.attribute_name='Temperature';bb=n.new('ShaderNodeBlackbody');l.new(at.outputs['Fac'],bb.inputs['Temperature']);l.new(bb.outputs[0],p.inputs['Emission Color']);div=n.new('ShaderNodeMath');div.operation='DIVIDE';div.inputs[1].default_value=1450;l.new(at.outputs['Fac'],div.inputs[0]);pw=n.new('ShaderNodeMath');pw.operation='POWER';pw.inputs[1].default_value=8;l.new(div.outputs[0],pw.inputs[0]);l.new(pw.outputs[0],p.inputs['Emission Strength'])
 crust=bpy.data.materials.new('Cooling basalt crust');crust.use_nodes=True;cp=crust.node_tree.nodes.get('Principled BSDF');cp.inputs['Base Color'].default_value=(.009,.008,.007,1);cp.inputs['Roughness'].default_value=.92
 cn=crust.node_tree.nodes;cl=crust.node_tree.links;no=cn.new('ShaderNodeTexNoise');no.inputs['Scale'].default_value=95;no.inputs['Detail'].default_value=4;bu=cn.new('ShaderNodeBump');bu.inputs['Strength'].default_value=.65;bu.inputs['Distance'].default_value=.006;cl.new(no.outputs['Fac'],bu.inputs['Height']);cl.new(bu.outputs['Normal'],cp.inputs['Normal'])
elif KIND=='mud':
 p.inputs['Base Color'].default_value=(.055,.026,.009,1);p.inputs['Roughness'].default_value=.27;p.inputs['Coat Weight'].default_value=.35;bump.inputs['Distance'].default_value=.014
elif KIND=='foam':
 p.inputs['Base Color'].default_value=(.48,.55,.59,1);p.inputs['Roughness'].default_value=.32;p.inputs['Transmission Weight'].default_value=.38;p.inputs['Roughness'].default_value=.15;p.inputs['Subsurface Weight'].default_value=.08;p.inputs['Subsurface Radius'].default_value=(.05,.075,.1);noise.inputs['Scale'].default_value=110;bump.inputs['Distance'].default_value=.001;bump.inputs['Strength'].default_value=.15
else:
 p.inputs['Transmission Weight'].default_value=1;p.inputs['Base Color'].default_value=(.98,.99,1,1);bump.inputs['Strength'].default_value=0
 absorb=n.new('ShaderNodeVolumeAbsorption');absorb.inputs['Color'].default_value=(.42,.79,.89,1);absorb.inputs['Density'].default_value=.45;l.new(absorb.outputs[0],n.get('Material Output').inputs['Volume'])
 if KIND=='blood':
  p.inputs['Base Color'].default_value=(.27,.003,.008,1);p.inputs['Transmission Weight'].default_value=.45;p.inputs['Roughness'].default_value=.13;absorb.inputs['Color'].default_value=(.45,.002,.006,1);absorb.inputs['Density'].default_value=3
 if KIND in ['healing','spirit']:
  p.inputs['Emission Color'].default_value=(.02,.65,1,1) if KIND=='healing' else (.02,1,.45,1);p.inputs['Emission Strength'].default_value=1.1;p.inputs['Roughness'].default_value=.055
s.use_nodes=True;cn=s.node_tree.nodes;cn.clear();rl=cn.new('CompositorNodeRLayers');gl=cn.new('CompositorNodeGlare');gl.glare_type='FOG_GLOW';gl.quality='HIGH';gl.threshold=1.5 if KIND in ['lava','healing','spirit'] else 1000;gl.mix=-.92;outNode=cn.new('CompositorNodeComposite');s.node_tree.links.new(rl.outputs['Image'],gl.inputs['Image']);s.node_tree.links.new(gl.outputs['Image'],outNode.inputs['Image'])

for name,loc,power,size,sy in [('Long reflection',(-1,-3,4.8),1200,6,1.5),('Vertical reflection',(3,1,2.5),900,1.1,5),('Rim',(-3,2,3),850,3,2)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power*(.35 if KIND=='foam' else .12 if KIND=='lava' else 1);d.shape='RECTANGLE';d.size=size;d.size_y=sy;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-15,1.903125));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1.903125))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=10.5;s.camera=cam
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1);temp=bpy.context.object;iv=np.array([list(v.co) for v in temp.data.vertices]);ifa=np.array([list(p.vertices) for p in temp.data.polygons]);bpy.data.objects.remove(temp,do_unlink=True)
def coords(p):return np.column_stack((p[:,0]/.4-5.25,(p[:,2]-.9)/.4,p[:,1]/.4))
crustObj=None;births=np.full(180000,10000);seen=0
for bf in range(120):
 br=gzip.decompress((R/'viscous-cache'/f'{bf:04}.gz').read_bytes());count=len(br)//24;births[seen:count]=bf;seen=count
foamObj=None;obj=None;start=time.time();args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [];frames=range(120) if '--full' in args else [50]
for f in frames:
 if KIND=='lava':
  p.inputs['Emission Strength'].default_value=1.4*np.exp(-max(0,f/30-1.7)*.9)
 if obj:
  me=obj.data;bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(me)
 raw=gzip.decompress((cache/f'{f:04}.mesh.gz').read_bytes());nv,nf,nd=struct.unpack_from('<III',raw,4);extent=np.array(manifest['config']['extent']);off=32;verts=np.frombuffer(raw,'<u2',nv*3,off).reshape(-1,3)/65535*extent;off+=nv*6;off+=nv*6+nv;faces=np.frombuffer(raw,'<u4',nf*3,off).reshape(-1,3);off+=nf*12;drops=np.frombuffer(raw,'<u2',nd*3,off).reshape(-1,3)/65535*extent;off+=nd*6;radii=np.frombuffer(raw,'<f4',nd,off)
 verts=coords(verts);faces=faces[:,[0,2,1]];droppos=coords(drops)
 if nd:
  dv=(iv[None]*radii[:,None,None]/.4+droppos[:,None]).reshape(-1,3);df=(ifa[None]+np.arange(nd)[:,None,None]*len(iv)+nv).reshape(-1,3);verts=np.concatenate((verts,dv));faces=np.concatenate((faces,df))
 me=bpy.data.meshes.new('Native FLIP surface');me.from_pydata(verts.tolist(),[],faces.tolist());me.update();obj=bpy.data.objects.new('Water',me);bpy.context.collection.objects.link(obj);me.materials.append(m)
 for poly in me.polygons:poly.use_smooth=True
 if KIND=='lava':
  # Persistent FLIP particle IDs advect the crust geometry with the liquid.
  if crustObj:
   old=crustObj.data;bpy.data.objects.remove(crustObj,do_unlink=True);bpy.data.meshes.remove(old)
  rawp=gzip.decompress((R/'viscous-cache'/f'{f:04}.gz').read_bytes());count=len(rawp)//24;pp=coords(np.frombuffer(rawp,'<f4',count*3).reshape(-1,3));cv=[];cf=[]
  from mathutils.kdtree import KDTree
  kd=KDTree(count)
  for pid,pt in enumerate(pp):kd.insert(Vector(pt),pid)
  kd.balance();tempattr=me.attributes.new('Temperature','FLOAT','POINT')
  for vi,pt in enumerate(verts):
   _,pid,_=kd.find(Vector(pt));age=max(0,(f-births[pid])/30);tempattr.data[vi].value=850+700*np.exp(-age*.8)
  # Blender's BVH avoids an external scipy dependency in its Python runtime.
  from mathutils.bvhtree import BVHTree
  tree=BVHTree.FromPolygons([Vector(v) for v in verts[:nv]],faces[:nf].tolist(),all_triangles=True)
  for pid in range(0,count,5):
   age=(f-births[pid])/30
   if age<.06:continue
   q,norm,idx,dist=tree.find_nearest(Vector(pp[pid]))
   if q is None or dist>.06:continue
   rng=np.random.default_rng(pid+755);normal=np.array(norm);u=np.cross(normal,[0,1,0])
   if np.linalg.norm(u)<.01:u=np.cross(normal,[1,0,0])
   u/=np.linalg.norm(u);v=np.cross(normal,u);rad=rng.uniform(.045,.115)*min(1,age/.45);thick=.007;center=np.array(q)+normal*.004;off=len(cv);nside=5
   angles=np.arange(nside)*np.pi*2/nside+rng.uniform(0,6.28);rads=rad*rng.uniform(.6,1.2,nside)
   ring=[center+r*(np.cos(a)*u+np.sin(a)*v) for a,r in zip(angles,rads)]
   cv.extend([x+normal*h for h in [0,thick] for x in ring]);cf.extend([tuple(off+j for j in range(4,-1,-1)),tuple(off+j for j in range(5,10))]);cf.extend([(off+j,off+(j+1)%5,off+(j+1)%5+5,off+j+5) for j in range(5)])
  cm=bpy.data.meshes.new('Advected solid crust plates');cm.from_pydata(cv,[],cf);cm.materials.append(crust);crustObj=bpy.data.objects.new('Basalt crust',cm);bpy.context.collection.objects.link(crustObj)
 if KIND=='foam':
  obj.hide_render=True
  if foamObj:
   old=foamObj.data;bpy.data.objects.remove(foamObj,do_unlink=True);bpy.data.meshes.remove(old)
  # Stable primary particle indices provide bubble centers, rather than random per-frame decoration.
  rawp=gzip.decompress((R/'water-shared-cache'/f'{f:04}.gz').read_bytes());count=len(rawp)//24;pp=np.frombuffer(rawp,'<f4',count*3).reshape(-1,3)[::2];bp=coords(pp);ids=np.arange(len(pp));br=.025+.017*(.5+.5*np.sin(ids*17.13))**3
  bv=(iv[None]*br[:,None,None]+bp[:,None]).reshape(-1,3);bf=(ifa[None]+np.arange(len(bp))[:,None,None]*len(iv)).reshape(-1,3)
  bm=bpy.data.meshes.new('Aerated cells');bm.from_pydata(bv.tolist(),[],bf.tolist());bm.materials.append(m);foamObj=bpy.data.objects.new('Foam cells',bm);bpy.context.collection.objects.link(foamObj)
  for poly in bm.polygons:poly.use_smooth=True
 s.render.filepath=str(out/f'{f:04}.jpg');bpy.ops.render.render(write_still=True);print('FRAME',f,round(time.time()-start,1),flush=True)
print('COMPLETE',flush=True)
