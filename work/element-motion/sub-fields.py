import bpy,json,gzip,struct,sys,time
from pathlib import Path
import numpy as np
from mathutils import Vector
KIND=sys.argv[sys.argv.index('--kind')+1] if '--kind' in sys.argv else 'metal'
R=Path(__file__).resolve().parent;O=R.parent.parent/'outputs/cybrdelic-type/elements/motion';cache=O/'water/cache/material';manifest=json.loads((cache/'manifest.json').read_text());out=R/'subelements'/f'photo-{KIND}-frames';out.mkdir(parents=True,exist_ok=True)
s=bpy.context.scene;bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=48;s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.adaptive_threshold=.06;s.cycles.max_bounces=12;s.cycles.transmission_bounces=10;s.cycles.glossy_bounces=6;s.cycles.diffuse_bounces=2;s.cycles.caustics_reflective=False;s.cycles.caustics_refractive=False;s.render.use_persistent_data=True;s.render.threads_mode='FIXED';s.render.threads=3;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=96;s.view_settings.view_transform='AgX'
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
sys.path.insert(0,str(R));from shared_motion import pose
out=R/'subelements'/f'field-{KIND}-frames';out.mkdir(exist_ok=True)
s.cycles.samples=32
s.use_nodes=True;n=s.node_tree.nodes;n.clear();l=s.node_tree.links;rl=n.new('CompositorNodeRLayers');g=n.new('CompositorNodeGlare');g.glare_type='FOG_GLOW';g.quality='HIGH';g.threshold=2;g.size=7;g.mix=-.82;co=n.new('CompositorNodeComposite');l.new(rl.outputs['Image'],g.inputs['Image']);l.new(g.outputs['Image'],co.inputs['Image'])
def mat(name,color,emission=0,rough=.3):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=.35
 p.inputs['Emission Color'].default_value=(*color,1);p.inputs['Emission Strength'].default_value=emission
 return m
warm=mat('Amber coherent field',(1,.26,.025),9);cool=mat('Blue opposing field',(.08,.42,1),10);white=mat('Restoration front',(.48,1,.68),7);dark=mat('Disordered matter',(.018,.008,.035),0,.65);gold=mat('Purified filaments',(.75,.47,.10),3);tissue=mat('Living fibers',(.027,.075,.018),0,.52)
restoration=[mat('Restoration '+str(i),(.04+.08*i/15,.10+.28*i/15,.035+.13*i/15),.9*(i/15)**2,.5) for i in range(16)]
objects=[]
def line(name,pts,radius,material):
 key=(material.name,round(radius,4))
 if key not in curves:
  cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.resolution_u=1;cu.bevel_depth=radius;cu.bevel_resolution=2
  ob=bpy.data.objects.new(name,cu);bpy.context.collection.objects.link(ob);cu.materials.append(material);objects.append(ob);curves[key]=cu
 cu=curves[key];sp=cu.splines.new('POLY');sp.points.add(len(pts)-1)
 for i,(pt,p) in enumerate(zip(sp.points,pts)):pt.co=(*p,1);pt.radius=max(.08,max(0,math.sin(math.pi*i/max(1,len(pts)-1)))**.25)
from functools import lru_cache
@lru_cache(maxsize=12000)
def center(u):
 p,d,_,_=pose(.08+1.6*u);return np.array([p[0],0,p[1]]),np.array([-d[1],0,d[0]])
frames=[int(sys.argv[sys.argv.index('--frame')+1])] if '--frame' in sys.argv else range(120) if '--full' in sys.argv else [35,65,90]
for f in frames:
 if "--resume" in sys.argv and KIND=="spirit" and (out/f"{f:04}.jpg").exists():continue
 for ob in objects:
  data=ob.data;bpy.data.objects.remove(ob,do_unlink=True);bpy.data.curves.remove(data)
 objects=[];curves={};t=f/30;front=np.clip((t-.08)/1.6,0,1);decay=max(0,1-max(0,t-3.1)/.9)
 if KIND=='healing':
  # A damaged fibrous ribbon exists before the light reaches it. Fiber ends
  # physically converge; the repaired surface remains after the light passes.
  for strand in range(96):
   off=.12*math.sin(strand*2.399)*(.3+.7*math.sin(strand*1.73)**2)
   for segment in range(12):
    a=segment/12;b=(segment+1)/12;age=t-(.08+1.6*(a+b)/2);repair=np.clip(age/.42,0,1);gap=(.01+.025*math.sin(strand*1.91+segment)**2)*(1-repair)
    pts=[]
    for u in np.linspace(a+gap,b-gap,15):
     c,no=center(u);curl=(1-repair)*.045*math.sin((u-a)/(b-a)*math.pi)*math.sin(strand*2.1+segment)
     pts.append(c+no*(off+curl+.018*math.sin(u*32+strand*2.4))+np.array([0,.07*math.sin(strand*2.399+u*9),0]))
    line('Reconnecting fiber',pts,.0012+.0018*math.sin(strand*1.8)**4,restoration[int(15*max(0,math.sin(math.pi*np.clip(age/.55,0,1))))] if 0<age<.55 else tissue)
  for k in range(0):
   u=front-k*.003
   if .002<u<.998 and t<2.2:
    c,no=center(u);pts=[c+no*q+np.array([0,-.04-.025*math.sin(q*25+k),0]) for q in np.linspace(-.18,.18,32)];line('Repair illumination',pts,.0018,white)
 elif KIND=='spirit':
  # Disordered filaments straighten into a coherent strand behind a moving front.
  for strand in range(64):
   pts=[];pure=[]
   for u in np.linspace(0,1,200):
    c,no=center(u);age=t-(.08+1.6*u);q=np.clip(age/.6,0,1);theta=u*25+strand*2.399
    dis=.17*math.sin(u*53+strand*1.8)+.065*math.sin(u*131+strand)
    offset=(1-q)*dis+q*(.04+.09*math.sin(u*13+strand*.12)**2)*math.cos(theta);p=c+no*offset+np.array([0,(1-q)*.13*math.sin(u*63+strand)+q*(.04+.09*math.sin(u*13+strand*.12)**2)*math.sin(theta),0]);pts.append(p)
   edgefront=float(np.clip(front+.065*math.sin(math.pi*front)*math.sin(strand*2.399),0,1));remaining=pts[min(199,int(edgefront*199)):];
   if len(remaining)>1:line('Spirit structure',remaining,.0025,dark)
   for u in np.linspace(0,max(.001,edgefront),160):
    c,no=center(u);theta=u*25+strand*2.399;age=t-(.08+1.6*u);q=np.clip(age/.6,0,1);dis=.17*math.sin(u*53+strand*1.8)+.065*math.sin(u*131+strand);pure.append(c+no*((1-q)*dis+q*(.04+.09*math.sin(u*13+strand*.12)**2)*math.cos(theta))+np.array([0,(1-q)*.13*math.sin(u*63+strand)+q*(.04+.09*math.sin(u*13+strand*.12)**2)*math.sin(theta),0]))
   if front>.01:line('Purified coherent structure',pure,.0015*decay,gold)
 else:
  # Counter-propagating field lines meet and exchange through a persistent sheath.
  for side in [-1,1]:
   for strand in range(28):
    pts=[];end=min(1,max(0,(t-.08)/1.6));start=0
    for u0 in np.linspace(start,max(.001,end),200):
     u=u0 if side==1 else 1-u0;c,no=center(u);theta=u*16+strand*2.399+side*t*2+.6*math.sin(u*31+strand);radius=(.025+.28*(strand/28)**2)*(.3+.7*math.sin(u*11+strand*.14-side*t*1.4)**2);c=c+no*(radius*math.cos(theta))+np.array([0,radius*math.sin(theta),0]);pts.append(c)
    if end>.01:line('Opposing energy field',pts,(.0007+.001*(strand%7==0))*decay,warm if side==1 else cool)
  if t>1:
   for j in range(4):
    u=.5+.2*math.sin(t*1.8+j*.4);c,no=center(u);pts=[]
    for a in np.linspace(0,math.tau,70):pts.append(c+no*(.15*math.cos(a))+np.array([0,.15*math.sin(a),0]))
    line('Exchange sheath',pts,.0008*decay,white)
 s.render.filepath=str(out/f'{f:04}.jpg');bpy.ops.render.render(write_still=True)
 print('FRAME',KIND,f,flush=True)
print('COMPLETE',KIND,flush=True)
