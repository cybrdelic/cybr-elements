"""Narrow studio reflection/transmission cards on a black camera background."""
import bpy,math
def narrow_cards():
 for i,(x,width,height,strength) in enumerate([(-2.5,.28,3.2,3.5),(3.1,.16,2.5,5)]):
  bpy.ops.mesh.primitive_plane_add(size=2,location=(x,2.2,2.1),rotation=(math.pi/2,0,0));ob=bpy.context.object;ob.name='Narrow optical light card '+str(i);ob.scale=(width/2,height/2,1);ob.visible_camera=False;ob.visible_diffuse=False;ob.visible_shadow=False
  m=bpy.data.materials.new(ob.name);m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;n.remove(n['Principled BSDF']);e=n.new('ShaderNodeEmission');e.inputs['Color'].default_value=(1,.98,.95,1);e.inputs['Strength'].default_value=strength;l.new(e.outputs[0],n['Material Output'].inputs['Surface']);ob.data.materials.append(m)
