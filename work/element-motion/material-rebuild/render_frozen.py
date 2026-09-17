from pathlib import Path
import sys,bpy,json,numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from common import *
s=setup(secondary_environment=True);s.view_settings.exposure=-.7
for light in bpy.data.lights:light.energy*=.62
data=json.loads((R/'ice-grains.json').read_text());parts=data['parts'];cohesion=np.load(R/'ice-cohesion.npz')
ice=scene.material('Fractured translucent ice',(.86,.95,1),.055,trans=.96,ior=1.31)
n=ice.node_tree.nodes;l=ice.node_tree.links;ab=n.new('ShaderNodeVolumeAbsorption');ab.inputs['Color'].default_value=(.67,.88,.96,1);ab.inputs['Density'].default_value=.85;scatter=n.new('ShaderNodeVolumeScatter');scatter.inputs['Color'].default_value=(.8,.91,1,1);scatter.inputs['Density'].default_value=.8;scatter.inputs['Anisotropy'].default_value=.25;add=n.new('ShaderNodeAddShader');l.new(ab.outputs[0],add.inputs[0]);l.new(scatter.outputs[0],add.inputs[1]);l.new(add.outputs[0],n['Material Output'].inputs['Volume'])
ray=n.new('ShaderNodeLightPath');clear=n.new('ShaderNodeBsdfTransparent');mix=n.new('ShaderNodeMixShader');l.new(ray.outputs['Is Shadow Ray'],mix.inputs[0]);l.new(n['Principled BSDF'].outputs[0],mix.inputs[1]);l.new(clear.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],n['Material Output'].inputs['Surface'])
water=scene.material('Remaining liquid during freezing',(.96,.99,1),.025,trans=1,ior=1.333)
air=scene.material('Internal ice air pockets',(.96,.99,1),.045,trans=1,ior=1.31)
objects=[]
for f in selected():
 for ob in objects:scene.remove(ob)
 objects=[];a=np.load(R/'data/ice'/f'{f:04}.npz');v=a['v'];fa=a['f']
 if len(v):
  if np.sum(v[fa[:,0]]*np.cross(v[fa[:,1]],v[fa[:,2]]))<0:fa=fa[:,[0,2,1]]
  keep=a['phase'][fa].mean(1)<.56
  if keep.any():objects.append(mesh('Unfrozen carrier',v,fa[keep],water))
 bubbles=[];grain_vertices=[];grain_faces=[];offset=0
 for index,part in enumerate(parts):
  t=part['transforms'][f]
  fraction=cohesion['fraction'][f,index]
  if fraction<.001:continue
  rot=cohesion['rotation'][index];cp=cohesion['p'][f,index];scale=fraction**(1/3)
  verts=np.array(part['vertices'])@rot.T*scale+cp;faces=np.array(part['faces'],dtype='i4');grain_vertices.append(verts);grain_faces.append(faces+offset);offset+=len(verts)
  bubbles.extend(np.array(part['bubbles'])@rot.T*scale+cp)
 if grain_vertices:
  ob=mesh('Persistent separate ice grains',np.concatenate(grain_vertices),np.concatenate(grain_faces),ice,smooth=False);objects.append(ob);bevel=ob.modifiers.new('Fine fracture-edge glints','BEVEL');bevel.width=.0012;bevel.segments=2
 if bubbles:objects.append(instance('Trapped air in frozen grains',np.array(bubbles),.0016,air,scale=np.tile([.65,.7,1.5],(len(bubbles),1)),inward=True))
 finish(s,'ice',f)
