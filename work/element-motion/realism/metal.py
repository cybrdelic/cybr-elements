import sys,math,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from common import *
s,cam=setup(128)
s.view_settings.exposure=-.5
for light in bpy.data.lights:light.energy*=.18
for node in s.world.node_tree.nodes:
 if node.type=='MAPPING':node.inputs['Rotation'].default_value[2]=2.6
 if node.type=='BACKGROUND' and node.inputs['Color'].is_linked:node.inputs['Strength'].default_value=.8
m=bpy.data.materials.new('Worn steel');m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF');p.inputs['Base Color'].default_value=(.26,.29,.32,1);p.inputs['Metallic'].default_value=1;p.inputs['Anisotropic'].default_value=.45
uv=n.new('ShaderNodeTexCoord')
def tex(suffix):
 t=n.new('ShaderNodeTexImage');t.image=bpy.data.images.load(str(R/'assets'/('metal_plate_02_'+suffix+'_2k.jpg')));t.image.colorspace_settings.name='Non-Color';l.new(uv.outputs['UV'],t.inputs[0]);return t
rough=tex('rough');ran=n.new('ShaderNodeMapRange');ran.inputs['From Min'].default_value=0;ran.inputs['From Max'].default_value=1;ran.inputs['To Min'].default_value=.10;ran.inputs['To Max'].default_value=.28;l.new(rough.outputs[0],ran.inputs['Value']);l.new(ran.outputs[0],p.inputs['Roughness'])
normal=tex('nor_gl');nm=n.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=.06;l.new(normal.outputs[0],nm.inputs['Color']);l.new(nm.outputs[0],p.inputs['Normal'])
metal=tex('metal');ran2=n.new('ShaderNodeMapRange');ran2.inputs['To Min'].default_value=.98;ran2.inputs['To Max'].default_value=1;l.new(metal.outputs[0],ran2.inputs['Value']);l.new(ran2.outputs[0],p.inputs['Metallic'])
obj=None;out=R/'metal-frames';out.mkdir(exist_ok=True);frames=list(range(120)) if '--full' in sys.argv else [20,42,75,105]
if '--frame' in sys.argv:frames=[int(sys.argv[sys.argv.index('--frame')+1])]
# The formed strip becomes one rigid steel body. It keeps its section on release.
bpy.ops.mesh.primitive_plane_add(size=100);floor=bpy.context.object;floor.visible_camera=False
fm=bpy.data.materials.new('Matte contact floor');fm.diffuse_color=(.006,.007,.008,1);floor.data.materials.append(fm)
bpy.ops.rigidbody.object_add();floor.rigid_body.type='PASSIVE';floor.rigid_body.friction=.65
floor.select_set(False);carrier=None
for f in range(120):
 s.frame_set(f+1)
 if f>51:
  obj.matrix_world=carrier.matrix_world
  if f in frames:s.render.filepath=str(out/f'{f:04}.png');bpy.ops.render.render(write_still=True)
  continue
 if obj:
  me=obj.data;bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(me)
 t=f/30;front=np.clip((t-.08)/1.6,0,1);count=max(2,int(front*450));us=np.linspace(0,front,count);verts=[];faces=[];arcs=[0];prev=None
 for i,u in enumerate(us):
  p0,d,_,_=pose(.08+1.6*float(u));c=np.array([p0[0],.05*math.sin(u*9),p0[1]]);no=np.array([-d[1],0,d[0]]);a=.8*math.sin(u*7+.35*math.sin(t*1.2))*min(1,t*2);side=no*math.cos(a)+np.array([0,1,0])*math.sin(a)
  if prev is not None:arcs.append(arcs[-1]+float(np.linalg.norm(c-prev)))
  prev=c.copy()
  for j in range(9):
   w=(j-4)/4;width=.24+.025*math.sin(u*17);co=c+side*w*width;co[1]+=.035*w*w+.008*math.sin(u*71+w*8)*abs(w)**6;verts.append(co)
  if i:
   for j in range(8):k=(i-1)*9+j;faces.append((k,k+1,k+10,k+9))
 me=bpy.data.meshes.new('Continuous steel sheet');me.from_pydata(verts,[],faces);me.materials.append(m);uvl=me.uv_layers.new(name='SteelUV')
 for lp in me.loops:vi=lp.vertex_index;uvl.data[lp.index].uv=(arcs[vi//9]*.7,vi%9/8*.45)
 for poly in me.polygons:poly.use_smooth=True
 obj=bpy.data.objects.new('Formed steel',me);bpy.context.collection.objects.link(obj);sol=obj.modifiers.new('Sheet gauge','SOLIDIFY');sol.thickness=.012;be=obj.modifiers.new('Physical edge','BEVEL');be.width=.003;be.segments=3
 obj.hide_render=front<.001
 if f==51:
  carrier=bpy.data.objects.new('Steel collision body',me.copy());bpy.context.collection.objects.link(carrier)
  bpy.context.view_layer.objects.active=carrier;carrier.select_set(True);bpy.ops.rigidbody.object_add();carrier.select_set(False)
  rb=carrier.rigid_body;rb.collision_shape='MESH';rb.mass=18;rb.friction=.65;rb.restitution=.08;rb.use_margin=True;rb.collision_margin=.01;rb.linear_damping=.08;rb.angular_damping=.12
  rb.kinematic=True;rb.keyframe_insert('kinematic',frame=1);rb.keyframe_insert('kinematic',frame=66);rb.kinematic=False;rb.keyframe_insert('kinematic',frame=67)
  carrier.rotation_euler.x=-.025;carrier.keyframe_insert('rotation_euler',frame=65);carrier.rotation_euler.x=-.03;carrier.keyframe_insert('rotation_euler',frame=66)
  for v in ['visible_camera','visible_diffuse','visible_glossy','visible_transmission','visible_shadow']:setattr(carrier,v,False)
  s.rigidbody_world.substeps_per_frame=12;s.rigidbody_world.solver_iterations=40;s.rigidbody_world.point_cache.frame_end=120
 if f in frames:s.render.filepath=str(out/f'{f:04}.png');bpy.ops.render.render(write_still=True)
 print('FRAME',f,flush=True)
