import bpy,json,gzip,struct,sys,time
from pathlib import Path
import numpy as np
from mathutils import Vector
KIND=sys.argv[sys.argv.index('--kind')+1] if '--kind' in sys.argv else 'metal'
R=Path(__file__).resolve().parent;O=R.parent.parent/'outputs/cybrdelic-type/elements/motion';cache=O/'water/cache/material';manifest=json.loads((cache/'manifest.json').read_text());out=R/'subelements'/f'{KIND}-frames';out.mkdir(parents=True,exist_ok=True)
s=bpy.context.scene;bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=16;s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.adaptive_threshold=.06;s.cycles.max_bounces=12;s.cycles.transmission_bounces=10;s.cycles.glossy_bounces=6;s.cycles.diffuse_bounces=2;s.cycles.caustics_reflective=False;s.cycles.caustics_refractive=False;s.render.use_persistent_data=True;s.render.threads_mode='FIXED';s.render.threads=3;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=96;s.view_settings.view_transform='AgX'
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
# Black camera plate with a studio environment available to reflection and transmission rays.
w=s.world;w.use_nodes=True;n=w.node_tree.nodes;n.clear();l=w.node_tree.links;world=n.new('ShaderNodeOutputWorld');mix=n.new('ShaderNodeMixShader');ray=n.new('ShaderNodeLightPath');env=n.new('ShaderNodeBackground');env.inputs['Color'].default_value=(.24,.36,.43,1);env.inputs['Strength'].default_value=.5;black=n.new('ShaderNodeBackground');black.inputs['Color'].default_value=(0,0,0,1);l.new(ray.outputs['Is Camera Ray'],mix.inputs[0]);l.new(env.outputs[0],mix.inputs[1]);l.new(black.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],world.inputs[0])
tc=n.new('ShaderNodeTexCoord');dot=n.new('ShaderNodeVectorMath');dot.operation='DOT_PRODUCT';dot.inputs[1].default_value=(.55,.15,.80);l.new(tc.outputs['Normal'],dot.inputs[0]);mapping=n.new('ShaderNodeMapRange');mapping.inputs['From Min'].default_value=-1;mapping.inputs['From Max'].default_value=1;l.new(dot.outputs['Value'],mapping.inputs['Value']);ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1]);stops=[(0,(.015,.02,.025)),(.28,(.025,.03,.035)),(.44,(.18,.30,.36)),(.53,(.012,.018,.022)),(.70,(.16,.23,.27)),(.86,(.10,.12,.14)),(1,(.02,.025,.03))]
for i,(pos,color) in enumerate(stops):
 el=ramp.color_ramp.elements[0] if i==0 else ramp.color_ramp.elements.new(pos);el.position=pos;el.color=(*color,1)
l.new(mapping.outputs['Result'],ramp.inputs[0]);l.new(ramp.outputs['Color'],env.inputs['Color']);env.inputs['Strength'].default_value=.8
for name,loc,power,size,sy in [('Long reflection',(-1,-3,4.8),1200,6,1.5),('Vertical reflection',(3,1,2.5),900,1.1,5),('Rim',(-3,2,3),850,3,2)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='RECTANGLE';d.size=size;d.size_y=sy;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-15,1.903125));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1.903125))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=10.5;s.camera=cam

import math
sys.path.insert(0,str(R));from shared_motion import pose,DATA
m=bpy.data.materials.new(KIND);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.44,.49,.55,1) if KIND=='metal' else (.025,.13,.016,1);p.inputs['Metallic'].default_value=1 if KIND=='metal' else 0;p.inputs['Roughness'].default_value=.2 if KIND=='metal' else .4
if KIND=='metal':p.inputs['Anisotropic'].default_value=.65
else:p.inputs['Subsurface Weight'].default_value=.15
noise=m.node_tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=180 if KIND=='metal' else 35;noise.inputs['Detail'].default_value=3;bump=m.node_tree.nodes.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.0015;bump.inputs['Strength'].default_value=.25;m.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height']);m.node_tree.links.new(bump.outputs['Normal'],p.inputs['Normal'])
leaf=m.copy();leaf.name='Leaf';leaf.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.05,.24,.016,1)
objects=[];frames=range(120) if '--full' in sys.argv else [40,60];start=time.time()
for f in frames:
 for ob in objects:
  me=ob.data;bpy.data.objects.remove(ob,do_unlink=True)
  if isinstance(me,bpy.types.Mesh):bpy.data.meshes.remove(me)
  else:bpy.data.curves.remove(me)
 objects=[];t=f/30;end=min(1.68,t);count=max(0,int((end-.08)*120))
 if count>=2:
  ts=np.linspace(.08,end,count);poses=[pose(float(q)) for q in ts];centers=np.array([[q[0][0],0,q[0][1]] for q in poses]);norm=np.array([[-q[1][1],0,q[1][0]] for q in poses]);uv=np.linspace(0,1,count)
  if KIND=='metal':
   for band in range(3):
    angle=.7*np.sin(uv*9+t*1.8+band*.5)+band*.35;width=.085+.04*np.sin(uv*5+band)**2;side=norm*np.cos(angle)[:,None]+np.array([0,1,0])*np.sin(angle)[:,None];c=centers+norm*(band-1)*.13;c[:,1]+=.07*np.sin(uv*13-t*2);c[:,2]-=max(0,t-1.8)**2*.65
    v=np.stack([c-side*width[:,None],c+side*width[:,None]],axis=1).reshape(-1,3);faces=[(2*i,2*i+1,2*i+3,2*i+2) for i in range(count-1)];me=bpy.data.meshes.new('Forged strip');me.from_pydata(v.tolist(),[],faces);me.materials.append(m);ob=bpy.data.objects.new('Metal band',me);bpy.context.collection.objects.link(ob);objects.append(ob);sol=ob.modifiers.new('Solid metal edge','SOLIDIFY');sol.thickness=.024;be=ob.modifiers.new('Rolled edges','BEVEL');be.width=.009;be.segments=3
    for face in me.polygons:face.use_smooth=True
  else:
   for strand in range(3):
    c=centers+norm*(.065*np.sin(uv*19+t*.6+strand*2))[:,None];c[:,1]=.055*np.cos(uv*19+strand*2);cu=bpy.data.curves.new('Growing vine','CURVE');cu.dimensions='3D';cu.bevel_depth=.038 if strand==0 else .025;cu.bevel_resolution=3;sp=cu.splines.new('POLY');sp.points.add(count-1)
    for pt,co in zip(sp.points,c):pt.co=(*co,1)
    ob=bpy.data.objects.new('Vine',cu);bpy.context.collection.objects.link(ob);cu.materials.append(m);objects.append(ob)
   v=[];fa=[]
   for i in range(5,count-3,8):
    for sign in [-1,1]:
     center=centers[i];direction=norm[i]*sign;length=.22+.11*math.sin(i*3.1)**2;tip=center+direction*length+np.array([.06,-.015,.10]);mid=(center+tip)/2;wing=np.array([poses[i][1][0],0,poses[i][1][1]])*.09+np.array([0,-.015,0]);j=len(v);v.extend([center.tolist(),(mid+wing).tolist(),tip.tolist(),(mid-wing).tolist(),(mid+np.array([0,-.02,.01])).tolist()]);fa.extend([(j,j+1,j+4),(j+1,j+2,j+4),(j+2,j+3,j+4),(j+3,j,j+4)])
   me=bpy.data.meshes.new('Leaves');me.from_pydata(v,[],fa);me.materials.append(leaf);ob=bpy.data.objects.new('Leaves',me);bpy.context.collection.objects.link(ob);objects.append(ob)
 s.render.filepath=str(out/f'{f:04}.jpg');bpy.ops.render.render(write_still=True)
 if f%20==0:print('FRAME',KIND,f,round(time.time()-start,1),flush=True)
print('COMPLETE',KIND,flush=True)
