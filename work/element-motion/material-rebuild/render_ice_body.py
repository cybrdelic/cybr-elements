"""Continuous frozen body with closed fracture surfaces and Bullet release."""
from pathlib import Path
import sys,bpy,json,numpy as np
from mathutils import Vector
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from common import *
s=setup(secondary_environment=False);s.view_settings.exposure=-.45
from optical_lighting import narrow_cards
narrow_cards()
for light in bpy.data.lights:light.energy*=.55
data=json.loads((R/'ice-fractures.json').read_text());freeze=data['freezeFrame']
ice=scene.material('Clear frozen carrier',(.97,.99,1),.032,trans=1,ior=1.31);n=ice.node_tree.nodes;l=ice.node_tree.links;ab=n.new('ShaderNodeVolumeAbsorption');ab.inputs['Color'].default_value=(.61,.85,.95,1);ab.inputs['Density'].default_value=.55;sc=n.new('ShaderNodeVolumeScatter');sc.inputs['Color'].default_value=(.77,.87,.94,1);sc.inputs['Density'].default_value=1.2;sc.inputs['Anisotropy'].default_value=.15;add=n.new('ShaderNodeAddShader');l.new(ab.outputs[0],add.inputs[0]);l.new(sc.outputs[0],add.inputs[1]);l.new(add.outputs[0],n['Material Output'].inputs['Volume'])
ray=n.new('ShaderNodeLightPath');clear=n.new('ShaderNodeBsdfTransparent');mix=n.new('ShaderNodeMixShader');l.new(ray.outputs['Is Shadow Ray'],mix.inputs[0]);l.new(n['Principled BSDF'].outputs[0],mix.inputs[1]);l.new(clear.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],n['Material Output'].inputs['Surface'])
sc.inputs['Density'].default_value=.12
pieces=[]
for i,part in enumerate(data['pieces']):
 v=np.array(part['vertices'])*.997;fa=np.array(part['faces'],dtype='i4');ob=mesh('Ice fracture '+str(i),v,fa,ice,smooth=True);ob.location=part['center'];pieces.append(ob)
 bevel=ob.modifiers.new('Fine fracture edges','BEVEL');bevel.width=.0008;bevel.segments=2;bevel.limit_method='ANGLE';bevel.angle_limit=.4
 bpy.context.view_layer.objects.active=ob;ob.select_set(True);bpy.ops.rigidbody.object_add();ob.select_set(False);rb=ob.rigid_body;rb.mass=max(.005,part['volume']*917);rb.collision_shape='CONVEX_HULL';rb.use_margin=True;rb.collision_margin=.0005;rb.friction=.55;rb.restitution=.06;rb.linear_damping=.04;rb.angular_damping=.10
 rb.kinematic=True;rb.keyframe_insert('kinematic',frame=1);rb.keyframe_insert('kinematic',frame=71);rb.kinematic=False;rb.keyframe_insert('kinematic',frame=72)
 ob.hide_render=True;ob.keyframe_insert('hide_render',frame=1);ob.keyframe_insert('hide_render',frame=freeze);ob.hide_render=False;ob.keyframe_insert('hide_render',frame=freeze+1)
 for fc in ob.animation_data.action.fcurves:
  for k in fc.keyframe_points:k.interpolation='CONSTANT'
bpy.ops.mesh.primitive_plane_add(size=100);floor=bpy.context.object;floor.visible_camera=False;floor.visible_glossy=False;floor.visible_transmission=False;bpy.ops.rigidbody.object_add();floor.rigid_body.type='PASSIVE';floor.rigid_body.friction=.7;floor.select_set(False)
# Neighboring fracture cells remain cohesive until impact stress breaks them.
centers=np.array([p['center'] for p in data['pieces']])
for i,part in enumerate(data['pieces']):
 for j in np.argsort(np.linalg.norm(centers-centers[i],axis=1))[1:3]:
  if j<=i or np.linalg.norm(centers[i]-centers[j])>.55:continue
  ob=bpy.data.objects.new('Brittle ice bond',None);bpy.context.collection.objects.link(ob);ob.location=(centers[i]+centers[j])*.5;bpy.context.view_layer.objects.active=ob;ob.select_set(True);bpy.ops.rigidbody.constraint_add();ob.select_set(False);c=ob.rigid_body_constraint;c.type='FIXED';c.object1=pieces[i];c.object2=pieces[j];c.use_breaking=True;c.breaking_threshold=.65;c.disable_collisions=True
s.rigidbody_world.substeps_per_frame=12;s.rigidbody_world.solver_iterations=30;s.rigidbody_world.point_cache.frame_end=120
requested=set(selected());carrier=None
for f in range(120):
 s.frame_set(f+1)
 if f not in requested:continue
 if carrier is not None:scene.remove(carrier);carrier=None
 if f<freeze:
  a=np.load(R/'data/ice'/f'{f:04}.npz');v=a['v'];fa=a['f']
  if len(v):
   if np.sum(v[fa[:,0]]*np.cross(v[fa[:,1]],v[fa[:,2]]))<0:fa=fa[:,[0,2,1]]
   carrier=mesh('Freezing continuous fluid',v,fa,ice,smooth=True)
 finish(s,'ice',f)
