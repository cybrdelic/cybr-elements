import sys,math,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from helpers import *
from mathutils import Matrix
K=sys.argv[sys.argv.index('--kind')+1];s,cam=setup(96);bloom(s,2,-.88);rng=np.random.default_rng(24)

def sculpture():
 with bpy.data.libraries.load(str(R/'assets/marble_bust_01_2k.blend'),link=False) as (a,b):b.objects=[name for name in a.objects if 'LOD0' in name]
 objs=[o for o in b.objects if o and o.type=='MESH']
 if not objs:
  with bpy.data.libraries.load(str(R/'assets/marble_bust_01_2k.blend'),link=False) as (a,b):b.objects=a.objects
  objs=sorted([o for o in b.objects if o and o.type=='MESH'],key=lambda o:len(o.data.vertices),reverse=True)[:1]
 src=max(objs,key=lambda o:len(o.data.vertices));bpy.context.collection.objects.link(src);src.location=(0,0,0);src.rotation_euler=(0,0,0);src.scale=(1,1,1)
 v=np.array([list(v.co) for v in src.data.vertices]);v-=np.array([(v[:,0].min()+v[:,0].max())/2,(v[:,1].min()+v[:,1].max())/2,(v[:,2].min()+v[:,2].max())/2]);v*=2.3/np.ptp(v[:,2]);src.data.vertices.foreach_set('co',v.ravel());src.data.update()
 for image in bpy.data.images:
  path=R/'assets/textures'/Path(image.filepath).name
  if path.exists():image.filepath=str(path);image.reload()
 return src,v

if K in ['spirit-projection','energy']:
 body,v=brandmark();body.location=(-3.35,.05,1.45) if K=='spirit-projection' else (.15,.08,1.5);body.rotation_euler.z=-.10
 if K=='spirit-projection':
  body.scale=(.35,.35,.35)
  ghost=body.copy();ghost.data=body.data.copy();bpy.context.collection.objects.link(ghost);gm=material('Refractive projected identity',(.58,.83,1),.06,trans=.86,ior=1.08);p=gm.node_tree.nodes.get('Principled BSDF');p.inputs['Emission Color'].default_value=(.10,.45,.85,1);p.inputs['Emission Strength'].default_value=.22;ghost.data.materials.clear();ghost.data.materials.append(gm)
  nt=gm.node_tree;layer=nt.nodes.new('ShaderNodeLayerWeight');layer.inputs[0].default_value=.22;ra=nt.nodes.new('ShaderNodeMapRange');ra.inputs['To Min'].default_value=.025;ra.inputs['To Max'].default_value=.8;nt.links.new(layer.outputs['Fresnel'],ra.inputs[0]);nt.links.new(ra.outputs[0],p.inputs['Emission Strength']);tr=nt.nodes.new('ShaderNodeBsdfTransparent');mix=nt.nodes.new('ShaderNodeMixShader');mix.inputs[0].default_value=.25;nt.links.new(tr.outputs[0],mix.inputs[1]);nt.links.new(p.outputs[0],mix.inputs[2]);nt.links.new(mix.outputs[0],nt.nodes.get('Material Output').inputs[0])
 else:
  # The two fields meet on a solid subject; the normal/roughness maps stay visible.
  for mi,m in enumerate(list(body.data.materials)):
   m=m.copy();body.data.materials[mi]=m;n=m.node_tree.nodes;l=m.node_tree.links;p=next((node for node in n if node.type=='BSDF_PRINCIPLED'),None)
   if not p:continue
   original=p.inputs['Base Color'].links[0].from_socket if p.inputs['Base Color'].is_linked else None
   dark=n.new('ShaderNodeMixRGB');dark.blend_type='MULTIPLY';dark.inputs[0].default_value=1;dark.inputs[2].default_value=(.018,.022,.03,1)
   if original:l.new(original,dark.inputs[1])
   else:dark.inputs[1].default_value=(.5,.5,.5,1)
   l.new(dark.outputs[0],p.inputs['Base Color']);p.inputs['Roughness'].default_value=.3
   co=n.new('ShaderNodeTexCoord');mapping=n.new('ShaderNodeMapping');l.new(co.outputs['Generated'],mapping.inputs[0]);noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=8;noise.inputs['Detail'].default_value=5;l.new(mapping.outputs[0],noise.inputs[0]);vor=n.new('ShaderNodeTexVoronoi');vor.feature='DISTANCE_TO_EDGE';vor.inputs['Scale'].default_value=32;l.new(noise.outputs['Color'],vor.inputs[0]);edge=n.new('ShaderNodeMapRange');edge.inputs['From Min'].default_value=.0;edge.inputs['From Max'].default_value=.026;edge.inputs['To Min'].default_value=1;edge.inputs['To Max'].default_value=0;edge.clamp=True;l.new(vor.outputs['Distance'],edge.inputs[0]);charge=n.new('ShaderNodeAttribute');charge.attribute_name='Charge';mult=n.new('ShaderNodeMath');mult.operation='MULTIPLY';l.new(edge.outputs[0],mult.inputs[0]);l.new(charge.outputs['Fac'],mult.inputs[1]);l.new(mult.outputs[0],p.inputs['Emission Strength']);polarity=n.new('ShaderNodeAttribute');polarity.attribute_name='Polarity';ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.025,.25,1,1);ramp.color_ramp.elements[1].color=(1,.20,.008,1);l.new(polarity.outputs['Fac'],ramp.inputs[0]);l.new(ramp.outputs[0],p.inputs['Emission Color'])
  charge=body.data.attributes.new('Charge','FLOAT','POINT');polarity=body.data.attributes.new('Polarity','FLOAT','POINT')
  gold,ge=emission('Warm field',(.95,.22,.02),15);blue,be=emission('Cool field',(.02,.30,1),15);arcs=[]
 for f in sorted(selected()):
  t=f/30;p0,d,on,_=pose(min(t,1.68))
  if K=='spirit-projection':
   separation=np.clip((t-.12)/.6,0,1);ghost.hide_render=t<.12;ghost.location=(p0[0],-.20-.25*separation,p0[1]+.45);ghost.rotation_euler=(0,0,-.1+.35*math.sin(t*.7));ghost.scale=(.35,.35,.35)
   # The detached form retains the source anatomy, silhouette and surface relief.
  else:
   pos=v+np.array(body.location);distance=np.sqrt((pos[:,0]-p0[0])**2+(pos[:,2]-p0[1])**2);envelope=np.exp(-distance**2/1.2)*(3+7*abs(math.sin(t*12)))*(1 if t<1.7 else math.exp(-(t-1.7)*2));charge.data.foreach_set('value',envelope);polarity.data.foreach_set('value',np.clip(.5+.5*np.sin(pos[:,2]*2-t*4),0,1));body.data.update()
   for ob in arcs:
    cu=ob.data;bpy.data.objects.remove(ob,do_unlink=True);bpy.data.curves.remove(cu)
   arcs=[]
   if .1<t<2.8:
    for sign,mat in [(-1,blue),(1,gold)]:
     pts=[]
     for u in np.linspace(max(0,(min(t,1.68)-.5-.08)/1.6),np.clip((min(t,1.68)-.08)/1.6,0,1),80):
      pp,dd,_,_=pose(.08+u*1.6);ofs=.08*sign+.015*math.sin(u*143);pts.append([pp[0]-dd[1]*ofs,-.35,pp[1]+dd[0]*ofs])
     if len(pts)>1:arcs.append(curve('Current transfer',pts,.004,mat))
  finish(s,K,f)
else:
 # Recognizable spirit koi with an articulated body, wet scales, fins and eyes.
 fish=[];bodymat=material('Pearlescent spirit scales',(.72,.65,.5),.22,metal=.12,trans=.07);pn=bodymat.node_tree.nodes.get('Principled BSDF');pn.inputs['Coat Weight'].default_value=.5;pn.inputs['Coat Roughness'].default_value=.045
 n=bodymat.node_tree.nodes;l=bodymat.node_tree.links;tc=n.new('ShaderNodeTexCoord');mp=n.new('ShaderNodeMapping');mp.inputs['Scale'].default_value=(3,1,1);l.new(tc.outputs['Generated'],mp.inputs[0]);noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=5;noise.inputs['Detail'].default_value=4;l.new(mp.outputs[0],noise.inputs[0]);ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.4;ramp.color_ramp.elements[0].color=(.045,.009,.003,1);ramp.color_ramp.elements[1].position=.6;ramp.color_ramp.elements[1].color=(.72,.69,.54,1);l.new(noise.outputs['Fac'],ramp.inputs[0]);l.new(ramp.outputs[0],pn.inputs['Base Color']);scale=n.new('ShaderNodeTexVoronoi');scale.inputs['Scale'].default_value=45;l.new(mp.outputs[0],scale.inputs[0]);bu=n.new('ShaderNodeBump');bu.inputs['Distance'].default_value=.003;bu.inputs['Strength'].default_value=.4;l.new(scale.outputs['Distance'],bu.inputs['Height']);l.new(bu.outputs[0],pn.inputs['Normal']);finmat=material('Thin translucent fins',(.66,.67,.48),.23,trans=.55,ior=1.36);eye=material('Wet dark eye',(.001,.002,.002),.025)
 for k in range(3):
  vs=[];fs=[];nx=80;nr=48
  for i,u in enumerate(np.linspace(0,1,nx)):
   x=.72-u*1.42;rad=(.025+.21*max(0,math.sin(math.pi*u))**.7)*(1-.65*u**3)
   for j,a in enumerate(np.arange(nr)*math.tau/nr):vs.append([x,rad*.68*math.sin(a),rad*math.cos(a)])
  for i in range(nx-1):
   for j in range(nr):fs.append((i*nr+j,i*nr+(j+1)%nr,(i+1)*nr+(j+1)%nr,(i+1)*nr+j))
  fs.extend([tuple(range(nr-1,-1,-1)),tuple(range((nx-1)*nr,nx*nr))]);ob=mesh('Spirit koi body',vs,fs,bodymat,True);root=bpy.data.objects.new('Koi motion',None);bpy.context.collection.objects.link(root);ob.parent=root;parts=[(ob,np.array(vs))]
  # Fan tail with fin rays represented by actual ridged geometry.
  for typ in ['tail','dorsal','left','right']:
   vv=[];ff=[]
   for i,u in enumerate(np.linspace(0,1,15)):
    for j,a in enumerate(np.linspace(-1,1,25)):
     if typ=='tail':co=[-.63-u*.42,.015*math.sin(j*math.pi)*u,u*a*.38]
     elif typ=='dorsal':co=[.25-a*.45,.012*math.sin(j*math.pi)*u,.16+u*.20*(1-a*a)]
     else:co=[.12-u*.40,(1 if typ=='left' else -1)*(.11+u*.26),a*u*.16-.07]
     vv.append(co)
   for i in range(14):
    for j in range(24):q=i*25+j;ff.append((q,q+1,q+26,q+25))
   fo=mesh('Flexible '+typ+' fin',vv,ff,finmat,True);fo.parent=root;parts.append((fo,np.array(vv)))
  for sign in [-1,1]:
   bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=12,radius=.037,location=(.53,sign*.086,.08));o=bpy.context.object;o.data.materials.append(eye);o.parent=root
  fish.append((root,parts))
 for f in sorted(selected()):
  t=f/30;purify=np.clip((t-.35)/1.9,0,1);pn.inputs['Emission Color'].default_value=(.10,.3,.16,1);pn.inputs['Emission Strength'].default_value=.15*purify;ramp.color_ramp.elements[0].color=(.012+.09*purify,.008+.075*purify,.006+.035*purify,1)
  for k,(root,parts) in enumerate(fish):
   ft=t-k*.23;p0,d,on,_=pose(min(max(ft,.08),1.68));root.hide_render=False;root.location=(p0[0],k*.14,p0[1]+(k-1)*.18);root.rotation_euler=(0,-math.atan2(d[1],d[0]),.05*math.sin(t*3+k));root.scale=(.90-k*.10,)*3
   for child in root.children:child.hide_render=ft<.08
   for ob,rest in parts:
    ob.hide_render=ft<.08;vv=rest.copy();tail=np.clip((.6-vv[:,0])/1.8,0,1);vv[:,1]+=np.sin(vv[:,0]*5-t*8+k)*tail**2*.18;ob.data.vertices.foreach_set('co',vv.ravel());ob.data.update()
  finish(s,K,f)
