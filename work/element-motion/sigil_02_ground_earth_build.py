"""Earth 02: visible ground stock, long curved lift, native floor impact."""
from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'sigil_02_alive_earth_render.py').read_text().replace("O=R/'sigil-02-alive'","O=R/'sigil-02-bending-ground'")
s=s.replace('s.frame_end=300','s.frame_end=390').replace('point_cache.frame_end=300','point_cache.frame_end=390')
s=s.replace("data=json.loads", "def smooth(x):\n x=max(0,min(1,x));return x*x*(3-2*x)\n\ndata=json.loads",1)
start=s.index(' arrival=max(');end=s.index(' objects.append(o)',start)
s=s[:start]+''' # Every full-size fracture is visible from the first frame, lying on the
 # floor. Its powered trajectory lifts and rolls it several world units.
 u=max(0,min(1,(center.x+4.05)/8.1));release=244
 startRotation=Vector((1.35+.45*math.sin(k*1.7),.55*math.sin(k*2.3),k*2.399))
 o.rotation_euler=startRotation
 rot=o.rotation_euler.to_matrix();bottom=min((rot@v.co).z for v in me.vertices)
 start=Vector((-3.7+7.4*u+.18*math.sin(k),1.35*math.sin(k*2.399),-bottom+.022))
 middle=Vector((-3.95+7.85*u,.85*math.sin(u*math.pi*2-.6),1.35+1.7*math.sin(math.pi*(u*.9+.08))))
 for f in range(1,163,2):
  t=(f-1)/30;a=smooth((t-.5-u*.55)/2.0);b=smooth((t-2.3-u*.5)/2.35)
  o.location=start.lerp(middle,a).lerp(center,b)
  o.rotation_euler=tuple((1-b)*(startRotation[j]+a*(2.0 if j==0 else -.7)*math.sin(k*.4+j)) for j in range(3))
  o.keyframe_insert('location',frame=f);o.keyframe_insert('rotation_euler',frame=f)
 o.location=center;o.rotation_euler=(0,0,0);o.keyframe_insert('location',frame=166);o.keyframe_insert('rotation_euler',frame=166)
 for f in range(169,release,3):
  gain=min(1,(f-166)/16)*(1-smooth((f-228)/12));wave=f*.062-center.x*.87+center.z*.35
  o.location=center+Vector((.012*math.sin(wave)+.006*math.sin(f*.13+k),.16*math.sin(wave)+.045*math.sin(f*.081+k*.41),.018*math.cos(wave*.87+k*.09)))*gain
  o.rotation_euler=(gain*.10*math.sin(wave+k*.83),gain*.12*math.sin(wave*.81+k*.37),gain*.045*math.cos(wave+k*.51));o.keyframe_insert('location',frame=f);o.keyframe_insert('rotation_euler',frame=f)
 # Settle the powered stress wave before handing all fragments to Bullet.
 # A simultaneous, nonoverlapping handoff avoids collision-correction pops.
 o.location=center;o.rotation_euler=(0,0,0);o.keyframe_insert('location',frame=241);o.keyframe_insert('rotation_euler',frame=241)
 o.keyframe_insert('location',frame=release);o.keyframe_insert('rotation_euler',frame=release)
 rb.kinematic=True;rb.keyframe_insert('kinematic',frame=1);rb.keyframe_insert('kinematic',frame=release);rb.kinematic=False;rb.keyframe_insert('kinematic',frame=release+1)
 for fc in o.animation_data.action.fcurves:
  for key in fc.keyframe_points:key.interpolation='CONSTANT' if fc.data_path=='rigid_body.kinematic' else 'LINEAR'
''' + s[end:]
# Debris is already on the ground. No visible object is spawned in midair.
start=s.index('# Released chips');end=s.index('s.rigidbody_world.substeps_per_frame',start)
s=s[:start]+'''# Small irregular gravel on the stage supplies a contact-scale cue. All of
# it exists at frame one and uses Bullet for the full shot.
rng=random.Random(97213)
for chip_index in range(92):
 radius=min(.065,.009/(1-rng.random()*.985)**.52)
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=radius,location=(rng.uniform(-4.2,4.2),rng.uniform(-1.4,1.4),radius*1.3));o=bpy.context.object;o.name=f'Ground gravel {chip_index:03}'
 for vert in o.data.vertices:vert.co*=rng.uniform(.72,1.25)
 o.data.materials.append(side);bpy.ops.rigidbody.object_add();rb=o.rigid_body;rb.collision_shape='CONVEX_HULL';rb.use_margin=True;rb.collision_margin=.0004;rb.mass=max(.0005,4/3*math.pi*radius**3*2600);rb.friction=.8;rb.restitution=.05;rb.linear_damping=.05;rb.angular_damping=.15;o.select_set(False);objects.append(o)
# Visible floor and actual passive Bullet collision geometry are the same mesh.
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,-.1));floor=bpy.context.object;floor.name='Ground / passive contact body';floor.scale=(40,40,.2);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
fm=bpy.data.materials.new('Black ground / stone contact');fm.use_nodes=True;fp=fm.node_tree.nodes.get('Principled BSDF');fp.inputs['Base Color'].default_value=(.009,.009,.009,1);fp.inputs['Roughness'].default_value=.8;fp.inputs['Specular IOR Level'].default_value=0;floor.data.materials.append(fm)
bpy.ops.rigidbody.object_add();floor.rigid_body.type='PASSIVE';floor.rigid_body.collision_shape='BOX';floor.rigid_body.use_margin=True;floor.rigid_body.collision_margin=.001;floor.rigid_body.friction=.86;floor.rigid_body.restitution=.035
floor.hide_render=True
bpy.ops.mesh.primitive_plane_add(size=40,location=(0,0,0));bpy.context.object.name='Ground / visible contact surface';bpy.context.object.data.materials.append(fm)
''' + s[end:]
s=s.replace('substeps_per_frame=8','substeps_per_frame=16').replace('solver_iterations=20','solver_iterations=40')
s=s.replace('location=(.65,-16.8,4.2375)','location=(.25,-17.2,5.1)').replace('Vector((0,0,2.8875))','Vector((0,0,1.55))').replace('cam.data.lens=44','cam.data.lens=48').replace("('Broad fill',(4,-4,1.5),180,5)","('Broad fill',(4,-4,3.7),180,5)")
s=s.replace('range(1,301)','range(1,391)').replace("f in [76,106,121,124,127,130,133,136,139,142,145,148,151,154,157,160,163,166]","f in [1,19,43,67,91,115,145,181,235,271,301,355,390]")
s=s.replace('frames=300','frames=390').replace('Authored rigid assembly and correlated stress-wave hold; native Bullet collisions and gravity for released chips and final collapse; unchanged photogrammetry stone material','All fractures visible on the ground at frame one; authored curved powered lift and hold; native Bullet inter-body and floor collisions after release. Ground gravel is dynamic throughout. Same scanned rock material.')
s=s.replace("out.mkdir(exist_ok=True)","out.mkdir(exist_ok=True)\nif '--floor-check' in sys.argv:out=O/'earth-ground-check-v4';out.mkdir(exist_ok=True)")
s=s.replace("s=bpy.context.scene;", "if '--release-check' in sys.argv:out=O/'earth-release-check';out.mkdir(exist_ok=True)\ns=bpy.context.scene;")
s=s.replace("if (full or f in [1,19,43,67,91,115,145,181,235,271,301,355,390])", "if (full or (f in [1,91,181,271,301,390] if '--floor-check' in sys.argv else f in [1,19,43,67,91,115,145,181,235,271,301,355,390]))")
s=s.replace("if (full or (f in", "if ((f in [229,244,249,255,261,270,300,390] if '--release-check' in sys.argv else full) or ('--release-check' not in sys.argv and (f in")
s=s.replace("f in [1,19,43,67,91,115,145,181,235,271,301,355,390])) and", "f in [1,19,43,67,91,115,145,181,235,271,301,355,390]))) and")
s=s.replace("if f%30==0:rows.append(dict(frame=f,finite=all(all(math.isfinite(v) for v in o.matrix_world.translation) for o in objects),minZ=min(o.matrix_world.translation.z for o in objects)))", "if f%30==0:\n  dg=bpy.context.evaluated_depsgraph_get();poses=[o.evaluated_get(dg).matrix_world for o in objects];rows.append(dict(frame=f,finite=all(all(math.isfinite(v) for v in a.translation) for a in poses),minZ=min(a.translation.z for a in poses),nearFloor=sum(a.translation.z<.5 for a in poses)))")
s=s.replace("if f%30==0:\n  dg=", "if f%30==0 or ('--physics-check' in sys.argv and 241<=f<=270):\n  dg=")
s=s.replace("nearFloor=sum(a.translation.z<.5 for a in poses)","nearFloor=sum(a.translation.z<.5 for a in poses),maxRise=max([a.translation.z-row['center'][2] for a,row in zip(poses,data['pieces'])])")
s=s.replace("if ((f in", "if '--physics-check' not in sys.argv and ((f in")
s=s.replace("O/('earth-report.json' if full else 'earth-pilot-report.json')", "O/('earth-physics-check.json' if '--physics-check' in sys.argv else 'earth-report.json' if full else 'earth-pilot-report.json')")
(R/'sigil_02_ground_earth_render.py').write_text(s)
print('Wrote grounded earth renderer: 390 frames, visible stock and passive floor.')
