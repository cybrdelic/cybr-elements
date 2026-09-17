import bpy, json
from pathlib import Path
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.fps=30;s.frame_end=60;s.gravity=(0,0,-.5)
bpy.ops.mesh.primitive_cube_add(size=.1,location=(0,0,2));body=bpy.context.object
bpy.ops.rigidbody.object_add();body.rigid_body.mass=1;body.rigid_body.collision_shape='BOX'
body.select_set(False)
bpy.ops.mesh.primitive_cube_add(size=.02,location=(0,0,2));anchor=bpy.context.object
bpy.ops.rigidbody.object_add();anchor.rigid_body.kinematic=True;anchor.rigid_body.collision_collections=[False]*19+[True]
anchor.keyframe_insert('location',frame=1);anchor.keyframe_insert('location',frame=3);anchor.location.x=1;anchor.keyframe_insert('location',frame=18)
for f in anchor.animation_data.action.fcurves:
 for k in f.keyframe_points:k.interpolation='LINEAR'
bpy.ops.object.empty_add(location=(0,0,2));joint=bpy.context.object
bpy.ops.rigidbody.constraint_add();c=joint.rigid_body_constraint;c.type='GENERIC_SPRING';c.spring_type='SPRING2';c.object1=anchor;c.object2=body;c.disable_collisions=True
for axis in 'xyz':
 setattr(c,'use_spring_'+axis,True);setattr(c,'spring_stiffness_'+axis,400);setattr(c,'spring_damping_'+axis,32)
c.enabled=True;c.keyframe_insert('enabled',frame=1);c.keyframe_insert('enabled',frame=30);c.enabled=False;c.keyframe_insert('enabled',frame=31)
for f in joint.animation_data.action.fcurves:
 for k in f.keyframe_points:k.interpolation='CONSTANT'
s.rigidbody_world.substeps_per_frame=16;s.rigidbody_world.solver_iterations=40;s.rigidbody_world.point_cache.frame_end=60
rows=[]
for frame in range(1,61):
 s.frame_set(frame)
 if frame in [1,10,16,25,30,45,60]:rows.append(dict(frame=frame,position=list(body.matrix_world.translation)))
assert abs(rows[4]['position'][0]-1)<.04,rows
assert rows[-1]['position'][2]<rows[4]['position'][2]-.15,rows
Path(__file__).with_name('sigil-native').joinpath('spring-check.json').write_text(json.dumps(rows,indent=2))
print('SPRING_CHECK',json.dumps(rows),flush=True)
