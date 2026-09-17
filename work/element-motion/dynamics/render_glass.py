import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from scene import *
s=setup(112);s.gravity=(0,0,-9.81);data=json.loads((R/'cache/glass-shells.json').read_text(encoding='utf-8'));mat=material('Thin annealed glass',(.98,1,.985),.012,trans=1,ior=1.52)
n=mat.node_tree.nodes;l=mat.node_tree.links;ab=n.new('ShaderNodeVolumeAbsorption');ab.inputs['Color'].default_value=(.68,.88,.73,1);ab.inputs['Density'].default_value=.5;l.new(ab.outputs[0],n.get('Material Output').inputs['Volume'])
wn=s.world.node_tree.nodes;wl=s.world.node_tree.links;wo=wn.get('World Output');ray=wn.new('ShaderNodeLightPath');mix=wn.new('ShaderNodeMixShader');env=wn.new('ShaderNodeBackground');tex=wn.new('ShaderNodeTexEnvironment');tex.image=bpy.data.images.load(str(ASSETS/'studio_small_08_2k.exr'));env.inputs['Strength'].default_value=.20;wl.new(tex.outputs[0],env.inputs[0]);wl.new(ray.outputs['Is Camera Ray'],mix.inputs[0]);wl.new(env.outputs[0],mix.inputs[1]);wl.new(wn.get('Background').outputs[0],mix.inputs[2]);wl.new(mix.outputs[0],wo.inputs[0])
wl.new(ray.outputs['Is Reflection Ray'],mix.inputs[0]);wl.new(wn.get('Background').outputs[0],mix.inputs[1]);wl.new(env.outputs[0],mix.inputs[2])
objects=[]
for i,part in enumerate(data['parts']):
    # Ragged polygons need explicit from_pydata because their face sizes differ.
    me=bpy.data.meshes.new('Glass shell');me.from_pydata(part['vertices'],[],part['faces']);me.materials.append(mat);me.update()
    import bmesh
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free()
    ob=bpy.data.objects.new('Glass fragment '+str(i),me);bpy.context.collection.objects.link(ob);bpy.context.view_layer.objects.active=ob;ob.select_set(True);bpy.ops.rigidbody.object_add();ob.rigid_body.collision_shape='CONVEX_HULL';ob.rigid_body.mass=.055;ob.rigid_body.friction=.4;ob.rigid_body.restitution=.08;ob.rigid_body.use_margin=True;ob.rigid_body.collision_margin=.001;ob.rotation_mode='QUATERNION'
    for f,row in enumerate(part['transforms']):ob.location=row['position'];ob.rotation_quaternion=row['quaternion'];ob.keyframe_insert('location',frame=f+1);ob.keyframe_insert('rotation_quaternion',frame=f+1)
    ob.rigid_body.kinematic=True;ob.keyframe_insert('rigid_body.kinematic',frame=1);ob.keyframe_insert('rigid_body.kinematic',frame=61);ob.rigid_body.kinematic=False;ob.keyframe_insert('rigid_body.kinematic',frame=62)
    born=max(2,int((.08+np.array(part['uv'])[:,0].mean()/8*1.6)*30)+1)
    ob.hide_render=True;ob.keyframe_insert('hide_render',frame=1);ob.keyframe_insert('hide_render',frame=born-1);ob.hide_render=False;ob.keyframe_insert('hide_render',frame=born);ob.select_set(False);objects.append(ob)
s.frame_set(61)
for i,j in data['connections']:
    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(objects[i].matrix_world.translation+objects[j].matrix_world.translation)/2);ob=bpy.context.object;bpy.ops.rigidbody.constraint_add();c=ob.rigid_body_constraint;c.type='FIXED';c.object1=objects[i];c.object2=objects[j];c.use_breaking=True;c.breaking_threshold=.025;c.disable_collisions=True
s.rigidbody_world.substeps_per_frame=12;s.rigidbody_world.solver_iterations=30;s.rigidbody_world.point_cache.frame_start=59;s.rigidbody_world.point_cache.frame_end=120
selected=set(frames())
for f in range(120):
    s.frame_set(f+1)
    if f not in selected:continue
    finish(s,'glass',f)
(R/'glass-mechanism.json').write_text(json.dumps({'solver':'Bullet rigid bodies and breakable fixed connections','pieces':len(objects),'connections':len(data['connections']),'thickness':.016,'formation':'Persistent fragments throughout; guided before dynamic release, with no geometry substitution','limits':'Authored fragment guidance and pre-fracture topology; not thermomechanical glass blowing'},indent=2),encoding='utf-8')
