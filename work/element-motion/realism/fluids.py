import bpy,json,gzip,struct,sys,time
from pathlib import Path
import numpy as np
from mathutils import Vector
KIND=sys.argv[sys.argv.index('--kind')+1] if '--kind' in sys.argv else 'foam'
R=Path(__file__).resolve().parent.parent;O=R.parent.parent/'outputs/cybrdelic-type/elements/motion';cache=O/('water/cache/viscous' if KIND in ['lava','mud'] else 'water/cache/material');manifest=json.loads((cache/'manifest.json').read_text());out=R/'realism'/f'{KIND}-frames';out.mkdir(parents=True,exist_ok=True)
s=bpy.context.scene;bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=96;s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.adaptive_threshold=.025;s.cycles.max_bounces=12;s.cycles.transmission_bounces=10;s.cycles.glossy_bounces=6;s.cycles.diffuse_bounces=2;s.cycles.caustics_reflective=False;s.cycles.caustics_refractive=False;s.render.use_persistent_data=True;s.render.threads_mode='FIXED';s.render.threads=3;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=96;s.view_settings.view_transform='AgX'
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
 p.inputs['Base Color'].default_value=(.007,.004,.002,1);p.inputs['Roughness'].default_value=.87
 vor=n.new('ShaderNodeTexVoronoi');vor.feature='DISTANCE_TO_EDGE';vor.inputs['Scale'].default_value=9
 ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.51;ramp.color_ramp.elements[0].color=(.0001,0,0,1);ramp.color_ramp.elements[1].position=.68;ramp.color_ramp.elements[1].color=(1,.16,.002,1);hot=ramp.color_ramp.elements.new(.59);hot.color=(.01,.0001,0,1);noise.inputs['Scale'].default_value=8;l.new(noise.outputs['Fac'],ramp.inputs[0]);l.new(ramp.outputs['Color'],p.inputs['Emission Color']);p.inputs['Emission Strength'].default_value=9
 # Slow crust drift provides a moving material coordinate field over the viscous geometry.
 tc=n.new('ShaderNodeTexCoord');drift=n.new('ShaderNodeVectorMath');drift.operation='ADD';l.new(tc.outputs['Object'],drift.inputs[0]);l.new(drift.outputs['Vector'],vor.inputs['Vector']);l.new(drift.outputs['Vector'],noise.inputs['Vector'])
elif KIND=='mud':
 p.inputs['Base Color'].default_value=(.023,.016,.008,1);p.inputs['Roughness'].default_value=.48;p.inputs['Coat Weight'].default_value=.22;bump.inputs['Distance'].default_value=.008;noise.inputs['Scale'].default_value=48;bump.inputs['Strength'].default_value=.6
elif KIND=='foam':
 p.inputs['Base Color'].default_value=(.97,.99,1,1);p.inputs['Transmission Weight'].default_value=1;p.inputs['Roughness'].default_value=.055;p.inputs['IOR'].default_value=1.333;bump.inputs['Strength'].default_value=0
 if 'Thin Film Thickness' in p.inputs:p.inputs['Thin Film Thickness'].default_value=320;p.inputs['Thin Film IOR'].default_value=1.33
else:
 p.inputs['Transmission Weight'].default_value=1;p.inputs['Base Color'].default_value=(.98,.99,1,1);bump.inputs['Strength'].default_value=0
 absorb=n.new('ShaderNodeVolumeAbsorption');absorb.inputs['Color'].default_value=(.42,.79,.89,1);absorb.inputs['Density'].default_value=.45;l.new(absorb.outputs[0],n.get('Material Output').inputs['Volume'])
 if KIND=='blood':
  p.inputs['Base Color'].default_value=(.07,.001,.003,1);p.inputs['Transmission Weight'].default_value=.1;p.inputs['Roughness'].default_value=.16;p.inputs['Coat Weight'].default_value=.3;absorb.inputs['Color'].default_value=(.45,.002,.006,1);absorb.inputs['Density'].default_value=14
 if KIND in ['healing','spirit']:
  p.inputs['Emission Color'].default_value=(.02,.65,1,1) if KIND=='healing' else (.02,1,.45,1);p.inputs['Emission Strength'].default_value=.035;p.inputs['Roughness'].default_value=.055
s.use_nodes=True;cn=s.node_tree.nodes;cn.clear();rl=cn.new('CompositorNodeRLayers');gl=cn.new('CompositorNodeGlare');gl.glare_type='FOG_GLOW';gl.quality='HIGH';gl.threshold=1.5 if KIND in ['lava','healing','spirit'] else 1000;gl.mix=-.92;outNode=cn.new('CompositorNodeComposite');s.node_tree.links.new(rl.outputs['Image'],gl.inputs['Image']);s.node_tree.links.new(gl.outputs['Image'],outNode.inputs['Image'])

for name,loc,power,size,sy in [('Long reflection',(-1,-3,4.8),1200,6,1.5),('Vertical reflection',(3,1,2.5),900,1.1,5),('Rim',(-3,2,3),850,3,2)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power*(.7 if KIND=='foam' else .12 if KIND=='lava' else .55 if KIND in ['healing','spirit','blood'] else .65 if KIND=='mud' else 1);d.shape='RECTANGLE';d.size=size;d.size_y=sy;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-15,1.903125));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1.903125))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=10.5;s.camera=cam
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1);temp=bpy.context.object;iv=np.array([list(v.co) for v in temp.data.vertices]);ifa=np.array([list(p.vertices) for p in temp.data.polygons]);bpy.data.objects.remove(temp,do_unlink=True)
def coords(p):return np.column_stack((p[:,0]/.4-5.25,(p[:,2]-.9)/.4,p[:,1]/.4))
foamObj=None;obj=None;start=time.time();args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [];frames=range(120) if '--full' in args else [50]
for f in frames:
 if "--resume" in args and (out/f"{f:04}.jpg").exists():continue
 if KIND=='lava':
  drift.inputs[1].default_value=(-f/30*.4,0,f/30*.07);p.inputs['Emission Strength'].default_value=4*np.exp(-max(0,f/30-1.7)*.6)
 if obj:
  me=obj.data;bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(me)
 raw=gzip.decompress((cache/f'{f:04}.mesh.gz').read_bytes());nv,nf,nd=struct.unpack_from('<III',raw,4);extent=np.array(manifest['config']['extent']);off=32;verts=np.frombuffer(raw,'<u2',nv*3,off).reshape(-1,3)/65535*extent;off+=nv*6;off+=nv*6+nv;faces=np.frombuffer(raw,'<u4',nf*3,off).reshape(-1,3);off+=nf*12;drops=np.frombuffer(raw,'<u2',nd*3,off).reshape(-1,3)/65535*extent;off+=nd*6;radii=np.frombuffer(raw,'<f4',nd,off)
 verts=coords(verts);faces=faces[:,[0,2,1]];droppos=coords(drops)
 if nd:
  dv=(iv[None]*radii[:,None,None]/.4+droppos[:,None]).reshape(-1,3);df=(ifa[None]+np.arange(nd)[:,None,None]*len(iv)+nv).reshape(-1,3);verts=np.concatenate((verts,dv));faces=np.concatenate((faces,df))
 me=bpy.data.meshes.new('Native FLIP surface');me.from_pydata(verts.tolist(),[],faces.tolist());me.update();obj=bpy.data.objects.new('Water',me);bpy.context.collection.objects.link(obj);me.materials.append(m)
 for poly in me.polygons:poly.use_smooth=True
 if KIND=='foam':
  obj.hide_render=True
  if foamObj:
   old=foamObj.data;bpy.data.objects.remove(foamObj,do_unlink=True);bpy.data.meshes.remove(old)
  # Stable primary particle indices provide bubble centers, rather than random per-frame decoration.
  rawp=gzip.decompress((R/'water-shared-cache'/f'{f:04}.gz').read_bytes());count=len(rawp)//24;pp=np.frombuffer(rawp,'<f4',count*3).reshape(-1,3)[::2];bp=coords(pp);ids=np.arange(len(pp));bp+=np.column_stack([np.sin(ids*127.1),np.sin(ids*311.7),np.sin(ids*74.7)])*.008;u=(np.sin(ids*127.1)*43758.5453)%1;br=np.minimum(.052,.018/(1-u*.97)**.45)
  bv=(iv[None]*br[:,None,None]+bp[:,None]).reshape(-1,3);bf=(ifa[None]+np.arange(len(bp))[:,None,None]*len(iv)).reshape(-1,3)
  inner=(iv[None]*(br*.997)[:,None,None]+bp[:,None]).reshape(-1,3);bf=np.concatenate((bf,bf[:,[0,2,1]]+len(bv)));bv=np.concatenate((bv,inner))
  bm=bpy.data.meshes.new('Aerated cells');bm.from_pydata(bv.tolist(),[],bf.tolist());bm.materials.append(m);foamObj=bpy.data.objects.new('Foam cells',bm);bpy.context.collection.objects.link(foamObj)
  for poly in bm.polygons:poly.use_smooth=True
 s.render.filepath=str(out/f'{f:04}.jpg');bpy.ops.render.render(write_still=True);print('FRAME',f,round(time.time()-start,1),flush=True)
print('COMPLETE',flush=True)
