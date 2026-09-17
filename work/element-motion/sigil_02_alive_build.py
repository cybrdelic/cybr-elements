"""Preserve accepted material/framing; give the held earth actual secondary motion."""
from pathlib import Path
import json
R=Path(__file__).resolve().parent;O=R/'sigil-02-alive';O.mkdir(exist_ok=True)
(O/'contract.json').write_text(json.dumps(dict(scope=['water','earth','lightning'],feedback='Fire feels alive; water, earth and lightning do not',preserve=['Full approved 02 artwork','Pitch-black backdrop','Current material and camera treatments','Long hold','Fire and air media'],changes={'water':'Resolved circulation driven by smooth curl forces during the hold, replacing near-zero bulk velocity','earth':'Small correlated pressure-wave shifts, rocking fracture surfaces, and irregular physical chip release','lightning':'Non-looping stochastic discharge events, propagating leaders and short return pulses; persistent low corona'},review='CPU pilots and motion sequences before final rendering; then decoded full-film review',limitations='Bending forces and held earth poses are authored controls. Bullet handles released fragments. Lightning is an authored discharge visualization, not calibrated plasma physics.'),indent=2))
s=(R/'sigil_02_coherent_earth_render.py').read_text().replace("O=R/'sigil-02-coherent'","O=R/'sigil-02-alive'")
s=s.replace("(O/'earth-geometry.json')","(R/'sigil-02-coherent/earth-geometry.json')")
s=s.replace('import bpy,json,math,sys,time','import bpy,json,math,sys,time,random')
start=s.index(' for f in range(arrival+8,release,8):');end=s.index('\n rb.kinematic=True',start)
s=s[:start]+''' # Neighbouring fragments share a travelling stress wave, with different
 # inertia. Rotations expose real fracture faces and alter their shadows.
 for f in range(arrival+6,release,3):
  gain=min(1,(f-arrival)/14);wave=f*.062-center.x*.87+center.z*.35
  o.location=center+Vector((.012*math.sin(wave)+.006*math.sin(f*.13+k),.16*math.sin(wave)+.045*math.sin(f*.081+k*.41),.018*math.cos(wave*.87+k*.09)))*gain
  o.rotation_euler=(gain*.10*math.sin(wave+k*.83),gain*.12*math.sin(wave*.81+k*.37),gain*.045*math.cos(wave+k*.51));o.keyframe_insert('location',frame=f);o.keyframe_insert('rotation_euler',frame=f)
 # Preserve the instantaneous held pose when Bullet takes over.
 o.keyframe_insert('location',frame=release);o.keyframe_insert('rotation_euler',frame=release)
''' +s[end:]
start=s.index('s.rigidbody_world.substeps_per_frame')
s=s[:start]+'''# Released chips are irregular solid meshes with mass, gravity and Bullet
# contact. A heavy-tailed size distribution avoids an even point-cloud spray.
rng=random.Random(97213)
for chip_index in range(92):
 row=data['pieces'][rng.randrange(len(data['pieces']))];center=Vector(row['center']);k=row['seed'];birth=rng.randrange(76,169)
 candidates=[v for v in row['verts'] if v[1]<-.025]
 if not candidates:continue
 v=Vector(candidates[rng.randrange(len(candidates))]);startpos=center+v+Vector((0,-.025,0))
 radius=min(.065,.009/(1-rng.random()*.985)**.52)
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=radius,location=startpos);o=bpy.context.object;o.name=f'Shed fracture {chip_index:03}'
 for vert in o.data.vertices:vert.co*=rng.uniform(.72,1.25)
 o.scale=(rng.uniform(.65,1.3),rng.uniform(.45,.9),rng.uniform(.6,1.4));o.data.materials.append(side)
 bpy.ops.rigidbody.object_add();rb=o.rigid_body;rb.collision_shape='CONVEX_HULL';rb.use_margin=True;rb.collision_margin=.0004;rb.mass=max(.0005,4/3*math.pi*radius**3*2600);rb.friction=.72;rb.restitution=.08;rb.linear_damping=.05;rb.angular_damping=.12
 o.hide_render=True;o.keyframe_insert('hide_render',frame=1);o.keyframe_insert('hide_render',frame=birth-1);o.hide_render=False;o.keyframe_insert('hide_render',frame=birth)
 velocity=Vector((rng.uniform(-.13,.13),rng.uniform(-.22,-.07),rng.uniform(-.1,.18)))
 o.location=startpos-velocity/30;o.keyframe_insert('location',frame=birth-1);o.location=startpos;o.keyframe_insert('location',frame=birth)
 o.rotation_euler=(rng.random()*3,rng.random()*3,rng.random()*3);o.keyframe_insert('rotation_euler',frame=birth-1);o.rotation_euler.rotate_axis('X',rng.uniform(-.08,.08));o.keyframe_insert('rotation_euler',frame=birth)
 rb.kinematic=True;rb.keyframe_insert('kinematic',frame=1);rb.keyframe_insert('kinematic',frame=birth);rb.kinematic=False;rb.keyframe_insert('kinematic',frame=birth+1)
 for fc in o.animation_data.action.fcurves:
  for key in fc.keyframe_points:key.interpolation='CONSTANT' if fc.data_path in ['hide_render','rigid_body.kinematic'] else 'LINEAR'
 o.select_set(False);objects.append(o)
''' +s[start:]
s=s.replace('f in [76,166]','f in [76,106,121,124,127,130,133,136,139,142,145,148,151,154,157,160,163,166]')
s=s.replace('else 24;s.cycles','else 12;s.cycles').replace('else 1280;s.render.resolution_y=1080 if full else 720','else 960;s.render.resolution_y=1080 if full else 540')
s=s.replace('Authored rigid assembly and hold, native Bullet collisions and gravity after frame175; photogrammetry stone material','Authored rigid assembly and correlated stress-wave hold; native Bullet collisions and gravity for released chips and final collapse; unchanged photogrammetry stone material')
(R/'sigil_02_alive_earth_render.py').write_text(s)
print('Earth: retained fracture geometry/materials, moving stress wave, 92 irregular Bullet chips; CPU pilots first.')
