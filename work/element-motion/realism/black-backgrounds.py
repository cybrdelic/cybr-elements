from pathlib import Path
R=Path(__file__).resolve().parent
for name in ['fracture.py','grains.py','electric.py','metal.py']:
 p=R/name;s=p.read_text(encoding='utf-8')
 s=s.replace("plane_context(rock_material(gain=.008),y=.85)","# Pitch-black camera background; no backdrop geometry.")
 s=s.replace("if K in ['pressure','flight']:plane_context(rock_material(gain=.008),y=.65)","if K in ['pressure','flight']:pass")
 s=s.replace("floor=bpy.context.object;", "floor=bpy.context.object;floor.visible_camera=False;")
 s=s.replace("floor=bpy.context.object\n", "floor=bpy.context.object;floor.visible_camera=False\n")
 p.write_text(s,encoding='utf-8')
p=R/'particle-sim.py';s=p.read_text(encoding='utf-8');a=s.index(" if K in ['pressure','flight']:\n  birth[:]=0;");b=s.index(' history=[];',a)
s=s[:a]+''' for i,b in enumerate(birth):
  p,d,_,_=pose(float(b));a=rng.uniform(0,math.tau);rr=(.22 if K in ['pressure','flight'] else .12)*rng.random()**.5;pos[i]=[p[0]-d[1]*rr*math.cos(a),rr*math.sin(a),p[1]+d[0]*rr*math.cos(a)];vel[i]=[d[0]*(.25 if K in ['pressure','flight'] else .9),rng.normal(0,.12),d[1]*(.25 if K in ['pressure','flight'] else .9)]
''' +s[b:];p.write_text(s,encoding='utf-8')
print('Removed all backdrop geometry; invisible collision floors retained')
