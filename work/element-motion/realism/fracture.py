import sys,math,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from helpers import *
from mathutils import Matrix
K=sys.argv[sys.argv.index('--kind')+1] if '--kind' in sys.argv else 'ice'
s,cam=setup(128);s.cycles.transmission_bounces=20;s.cycles.max_bounces=24;s.frame_end=120;s.view_settings.exposure=-.25
# A photographed surface supplies something real to refract.
# Pitch-black camera background; no backdrop geometry.
mat=material('Glacial ice' if K=='ice' else 'Fractured soda lime glass',(1,1,1),.045 if K=='ice' else .009,trans=1,ior=1.31 if K=='ice' else 1.52)
n=mat.node_tree.nodes;l=mat.node_tree.links;p=n.get('Principled BSDF');noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=45;noise.inputs['Detail'].default_value=4
if K=='ice':
 p.inputs['Base Color'].default_value=(.72,.84,.91,1);p.inputs['Transmission Weight'].default_value=.60;p.inputs['Subsurface Weight'].default_value=.22;p.inputs['Subsurface Radius'].default_value=(.055,.075,.10);p.inputs['Roughness'].default_value=.18
 bump=n.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.002;bump.inputs['Strength'].default_value=.28;l.new(noise.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs[0],p.inputs['Normal'])
 cloud=n.new('ShaderNodeTexNoise');cloud.inputs['Scale'].default_value=6;cloud.inputs['Detail'].default_value=3;ra=n.new('ShaderNodeMapRange');ra.inputs['From Min'].default_value=.36;ra.inputs['From Max'].default_value=.7;ra.inputs['To Min'].default_value=.02;ra.inputs['To Max'].default_value=3.0;ra.clamp=True;l.new(cloud.outputs['Fac'],ra.inputs[0]);scatter=n.new('ShaderNodeVolumeScatter');scatter.inputs[0].default_value=(.74,.86,.95,1);scatter.inputs['Anisotropy'].default_value=.25;l.new(ra.outputs[0],scatter.inputs['Density']);l.new(scatter.outputs[0],n.get('Material Output').inputs['Volume'])
else:
 ab=n.new('ShaderNodeVolumeAbsorption');ab.inputs[0].default_value=(.63,.86,.76,1);ab.inputs[1].default_value=.7;l.new(ab.outputs[0],n.get('Material Output').inputs['Volume'])

if K=='ice':
 p.inputs['Transmission Weight'].default_value=.9;p.inputs['Subsurface Weight'].default_value=.065;p.inputs['Base Color'].default_value=(.89,.96,1,1)
 tc=n.new('ShaderNodeTexCoord');mapping=n.new('ShaderNodeVectorMath');mapping.operation='SCALE';mapping.inputs['Scale'].default_value=1.8;l.new(tc.outputs['Object'],mapping.inputs[0])
 for suffix in ['NormalGL','Roughness']:
  tx=n.new('ShaderNodeTexImage');tx.image=bpy.data.images.load(str(R/'assets/ice002'/f'Ice002_2K-JPG_{suffix}.jpg'));tx.image.colorspace_settings.name='Non-Color';tx.projection='BOX';tx.projection_blend=.3;l.new(mapping.outputs[0],tx.inputs[0])
  if suffix=='NormalGL':
   normal=n.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.9;l.new(tx.outputs[0],normal.inputs['Color']);l.new(normal.outputs[0],p.inputs['Normal'])
  else:
   remap=n.new('ShaderNodeMapRange');remap.inputs['To Min'].default_value=.035;remap.inputs['To Max'].default_value=.36;l.new(tx.outputs[0],remap.inputs[0]);l.new(remap.outputs[0],p.inputs['Roughness'])

air=material('Enclosed ice fissures',(1,1,1),.012,trans=1,ior=1/1.31)
floorMat=material('Contact surface',(.008,.009,.011),.35)
bpy.ops.mesh.primitive_plane_add(size=100);floor=bpy.context.object;floor.visible_camera=False;floor.data.materials.append(floorMat);bpy.ops.rigidbody.object_add();floor.rigid_body.type='PASSIVE';floor.rigid_body.friction=.6;floor.select_set(False)
# Neighbouring cells share the same sampled boundary before release.
rng=np.random.default_rng(861);N=38 if K=='ice' else 48;steps=rng.uniform(.35,1.65,N);us=np.r_[0,np.cumsum(steps)/steps.sum()];centers=[];sides=[];width=[];rings=[]
for u in us:
 pos,d,_,_=pose(.08+1.6*float(u));c=np.array([pos[0],.12*math.sin(u*9),pos[1]]);side=np.array([-d[1],0,d[0]]);centers.append(c);sides.append(side);w=.18+.035*math.sin(u*23)+rng.uniform(-.025,.025);width.append(w)
 if K=='glass':c[1]=.03*math.sin(u*7)
 ring=[];tilt=rng.uniform(-.07,.07);phase=.17*math.sin(u*15)
 for a in np.arange(12)*math.tau/12:
  rr=w*(1+.11*math.sin(a*3+u*24));ring.append(c+side*rr*math.cos(a+phase)+np.array([0,rr*(.8 if K=='ice' else .32)*math.sin(a+phase),0])+np.array([d[0],0,d[1]])*tilt*math.cos(a))
 rings.append(ring)
centers=np.array(centers);sides=np.array(sides);objects=[]
for i in range(N):
 c0,c1=centers[i:i+2];side0,side1=sides[i:i+2];u=(us[i]+us[i+1])/2;born=int((.08+1.6*us[i])*30)+1
 if K in ['ice','glass']:born=64
 if K in ['ice','glass']:
  ring=rings[i]+rings[i+1];pieces=[(ring,[tuple(range(11,-1,-1)),tuple(range(12,24))]+[(j,(j+1)%12,(j+1)%12+12,j+12) for j in range(12)])]
 else:
  # Two triangles fracture from a common pane, with real millimetre edges.
  quad=[c0-side0*width[i]*1.35,c0+side0*width[i]*1.35,c1+side1*width[i+1]*1.35,c1-side1*width[i+1]*1.35];pieces=[]
  for ids in [(0,1,2),(0,2,3)]:
   tri=np.array([quad[j] for j in ids]);vv=[v+np.array([0,sign*.008,0]) for sign in [-1,1] for v in tri];fa=[(2,1,0),(3,4,5),(0,1,4,3),(1,2,5,4),(2,0,3,5)];pieces.append((vv,fa))
 for vi,(vv,fa) in enumerate(pieces):
  vv=np.array(vv);center=vv.mean(0);vv=(vv-center)*(.998 if K=='ice' else .99998);ob=mesh('Connected fracture cell',vv,fa,mat,True);ob.location=center
  import bmesh
  bm=bmesh.new();bm.from_mesh(ob.data);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(ob.data);bm.free()
  bevel=ob.modifiers.new('Worn wet edges' if K=='ice' else 'Broken pane edge','BEVEL');bevel.width=.018 if K=='ice' else .0004;bevel.segments=3
  bpy.context.view_layer.objects.active=ob;ob.select_set(True);bpy.ops.rigidbody.object_add();ob.select_set(False);rb=ob.rigid_body;rb.collision_shape='CONVEX_HULL';rb.mass=.7 if K=='ice' else .12;rb.friction=.42;rb.restitution=.08;rb.collision_margin=.001;rb.use_margin=True;rb.linear_damping=.06;rb.angular_damping=.1
  # Controlled formation is followed by free Bullet translation and rotation.
  release=64+int(rng.integers(0,8));rb.kinematic=True;rb.keyframe_insert('kinematic',frame=1);rb.keyframe_insert('kinematic',frame=release);rb.kinematic=False;rb.keyframe_insert('kinematic',frame=release+1)
  ob.location=center;ob.keyframe_insert('location',frame=1);ob.keyframe_insert('location',frame=release-1);ob.location=center+np.array([0,rng.uniform(-.002,.002),0]);ob.keyframe_insert('location',frame=release)
  ob.rotation_euler=(0,0,0);ob.keyframe_insert('rotation_euler',frame=release-1);ob.rotation_euler=(rng.uniform(-.009,.009),rng.uniform(-.004,.004),0);ob.keyframe_insert('rotation_euler',frame=release)
  ob.hide_render=True;ob.keyframe_insert('hide_render',frame=1);ob.keyframe_insert('hide_render',frame=max(1,born-1));ob.hide_render=False;ob.keyframe_insert('hide_render',frame=born)
  for fc in ob.animation_data.action.fcurves:
   for key in fc.keyframe_points:key.interpolation='CONSTANT' if fc.data_path in ['hide_render','rigid_body.kinematic'] else 'LINEAR'
  if K=='ice':
   av=[];af=[];base=np.array([[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]]);faces=np.array([[0,2,4],[2,1,4],[1,3,4],[3,0,4],[2,0,5],[1,2,5],[3,1,5],[0,3,5]])
   for pocket in range(9):
    co=rng.normal(0,[.017,.07,.065]);rad=rng.uniform(.002,.010);off=len(av);av.extend(base*np.array([1,.65,1.5])*rad+co);af.extend(faces+off)
   bubble=mesh('Trapped irregular air',av,af,air,True);bubble.parent=ob;bubble.hide_render=True;bubble.keyframe_insert('hide_render',frame=1);bubble.keyframe_insert('hide_render',frame=max(1,born-1));bubble.hide_render=False;bubble.keyframe_insert('hide_render',frame=born)
  objects.append(ob)
s.rigidbody_world.substeps_per_frame=16;s.rigidbody_world.solver_iterations=50;s.rigidbody_world.point_cache.frame_end=120
take=selected();shell=None
for f in range(120):
 s.frame_set(f+1)
 if K in ['ice','glass'] and f in take:
  if shell:
   old=shell.data;bpy.data.objects.remove(shell,do_unlink=True);bpy.data.meshes.remove(old);shell=None
  if f<63 and f>2:
   front=np.clip((f/30-.08)/1.6,0,1);j=min(N-1,int(np.searchsorted(us,front,side='right')-1));j=max(0,j);fraction=np.clip((front-us[j])/(us[j+1]-us[j]),0,1);rs=rings[:j+1]+[(np.array(rings[j])*(1-fraction)+np.array(rings[j+1])*fraction).tolist()];vv=np.array(rs).reshape(-1,3);fa=[]
   for a in range(len(rs)-1):
    for b in range(12):fa.append((a*12+b,a*12+(b+1)%12,(a+1)*12+(b+1)%12,(a+1)*12+b))
   fa.extend([tuple(range(11,-1,-1)),tuple(range((len(rs)-1)*12,len(rs)*12))]);shell=mesh('Continuous optical skin',vv,fa,mat,True);sub=shell.modifiers.new('Optical surface continuity','SUBSURF');sub.levels=2;sub.render_levels=2
   if K=='ice':
    texture=bpy.data.textures.get('Frozen surface relief') or bpy.data.textures.new('Frozen surface relief','CLOUDS');texture.noise_scale=.075;texture.noise_depth=2;disp=shell.modifiers.new('Uneven frozen surface','DISPLACE');disp.texture=texture;disp.texture_coords='GLOBAL';disp.strength=.09;disp.mid_level=.5
    fine=bpy.data.textures.get('Small frost relief') or bpy.data.textures.new('Small frost relief','CLOUDS');fine.noise_scale=.018;fine.noise_depth=1;micro=shell.modifiers.new('Small frost pits','DISPLACE');micro.texture=fine;micro.texture_coords='GLOBAL';micro.strength=.013;micro.mid_level=.5
 if f in take:finish(s,K,f)
(R/f'{K}-mechanism.json').write_text(json.dumps({'connectedCells':len(objects),'emitter':'shared-trail.json','formation':'controlled contiguous fracture cells','release':'Bullet rigid body contacts','frames':120}),encoding='utf-8')
