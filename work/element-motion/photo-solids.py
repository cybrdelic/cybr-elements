import bpy,json,math,random,time,sys,bmesh
import numpy as np
KIND=sys.argv[sys.argv.index('--kind')+1] if '--kind' in sys.argv else 'ice'
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from shared_motion import pose,DATA
random.seed(6271);data=json.loads((R/'earth-geometry.json').read_text());out=R/'subelements'/f'photo-{KIND}-frames';out.mkdir(parents=True,exist_ok=True)
s=bpy.context.scene;bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=64;s.cycles.use_denoising=True;s.cycles.denoiser="OPTIX";s.cycles.denoiser='OPTIX';s.cycles.max_bounces=16;s.cycles.transmission_bounces=12;s.render.use_persistent_data=True
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for dev in prefs.devices:dev.use=dev.type=='OPTIX'
s.render.engine='CYCLES';s.render.threads_mode='FIXED';s.render.threads=3;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=94;s.render.fps=30;s.frame_end=120;s.world.color=(0,0,0);s.world.use_nodes=True;s.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(0,0,0,1);s.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=0;s.view_settings.view_transform='AgX'
# Authored earthbending lift during the shared writing beat; full gravity on release.
s.gravity=(0,0,-.5);s.keyframe_insert('gravity',frame=1);s.keyframe_insert('gravity',frame=51);s.gravity=(0,0,-9.81);s.keyframe_insert('gravity',frame=65)
def material(name,color):
 m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=(*color,1);n.inputs['Roughness'].default_value=.92
 noise=m.node_tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=22;noise.inputs['Detail'].default_value=3;bump=m.node_tree.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.28;bump.inputs['Distance'].default_value=.001;m.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height']);m.node_tree.links.new(bump.outputs['Normal'],n.inputs['Normal']);return m
mats=[material('Stone '+str(i),(.09+i*.010,.060+i*.008,.032+i*.006)) for i in range(5)];floorMat=material('Ground',(.008,.009,.010))
bpy.ops.mesh.primitive_plane_add(size=100);floor=bpy.context.object;floor.data.materials.append(floorMat);bpy.ops.rigidbody.object_add();floor.rigid_body.type='PASSIVE';floor.rigid_body.friction=.85;floor.select_set(False)
def dielectric(name,col,rough=.01,ior=1.5,absorb=0,scatter=0):
 mat=bpy.data.materials.new(name);mat.use_nodes=True;nd=mat.node_tree.nodes;lk=mat.node_tree.links;pr=nd.get('Principled BSDF');pr.inputs['Base Color'].default_value=(1,1,1,1);pr.inputs['IOR'].default_value=ior;pr.inputs['Transmission Weight'].default_value=1;pr.inputs['Roughness'].default_value=rough
 if absorb or scatter:
  ab=nd.new('ShaderNodeVolumeAbsorption');ab.inputs['Color'].default_value=(*col,1);ab.inputs['Density'].default_value=absorb;sc=nd.new('ShaderNodeVolumeScatter');sc.inputs['Color'].default_value=(.82,.9,1,1);sc.inputs['Density'].default_value=scatter;sc.inputs['Anisotropy'].default_value=.3;add=nd.new('ShaderNodeAddShader');lk.new(ab.outputs[0],add.inputs[0]);lk.new(sc.outputs[0],add.inputs[1]);lk.new(add.outputs[0],nd.get('Material Output').inputs['Volume'])
 return mat
if KIND=='ice':
 mat=dielectric('Clear ice with cloudy interior',(.18,.6,.85),.012,1.31,.38,.17);nd=mat.node_tree.nodes;lk=mat.node_tree.links;pr=nd.get('Principled BSDF');no=nd.new('ShaderNodeTexNoise');no.inputs['Scale'].default_value=22;no.inputs['Detail'].default_value=4;ra=nd.new('ShaderNodeValToRGB');ra.color_ramp.elements[0].position=.48;ra.color_ramp.elements[0].color=(.008,.008,.008,1);ra.color_ramp.elements[1].position=.73;ra.color_ramp.elements[1].color=(.18,.18,.18,1);lk.new(no.outputs['Fac'],ra.inputs[0]);lk.new(ra.outputs['Color'],pr.inputs['Roughness']);rockMats=[mat,dielectric('Air pockets and fissures',(1,1,1),.006,1/1.31)]
elif KIND=='glass':rockMats=[dielectric('Optical glass',(.65,.9,.78),.009,1.52,.12)]
else:
 matrix=material('Quartz matrix',(.055,.037,.026));rockMats=[dielectric('Amethyst',(.38,.045,.62),.018,1.544,5),dielectric('Pale quartz',(.75,.65,.85),.023,1.544,.12),matrix]
if KIND=='crystal':
 rockMats[0].node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.62,.3,.8,1)
layers=[];layerMeshes={}
for idx,src in enumerate(data['pieces']):
 rng=np.random.default_rng(9100+idx);verts=[];faces=[];mi=[]
 def add(v,fa,matid=0):
  offset=len(verts);verts.extend(np.asarray(v).tolist());faces.extend([tuple(offset+j for j in face) for face in fa]);mi.extend([matid]*len(fa))
 if KIND=='ice':
  vs=np.array(src['verts']);vs-=vs.mean(0);vs/=np.linalg.norm(vs,axis=1).max();vs[:,1]*=.72;add(vs,src['faces'])
  # Small internal air pockets are actual refractive interfaces.
  for pocket in range(5):
   center=rng.normal(0,.035,3);rr=rng.uniform(.018,.055);v=np.array([[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]])*rr+center;fa=[(0,2,4),(2,1,4),(1,3,4),(3,0,4),(2,0,5),(1,2,5),(3,1,5),(0,3,5)];add(v,fa,1)
  for fissure in range(2):
   center=rng.normal(0,.025,3);normal=rng.normal(size=3);normal/=np.linalg.norm(normal);u=np.cross(normal,[0,1,0]);u/=np.linalg.norm(u);v=np.cross(normal,u);rr=rng.uniform(.08,.19);ring=[center+rr*(math.cos(a)*u+math.sin(a)*v) for a in np.linspace(0,math.tau,6,endpoint=False)];vv=[q+normal*side*.001 for side in [-1,1] for q in ring];fa=[tuple(range(5,-1,-1)),tuple(range(6,12))]+[(j,(j+1)%6,(j+1)%6+6,j+6) for j in range(6)];add(vv,fa,1)
 elif KIND=='glass':
  n=int(rng.integers(3,7));ang=np.sort(rng.uniform(0,math.tau,n));ring=np.array([[math.cos(a)*rng.uniform(.65,1),math.sin(a)*rng.uniform(.6,1)] for a in ang]);vv=[[q[0],side*.028,q[1]] for side in [-1,1] for q in ring];fa=[tuple(range(n)),tuple(range(2*n-1,n-1,-1))]+[(j,j+n,(j+1)%n+n,(j+1)%n) for j in range(n)];add(vv,fa)
 else:
  # Intergrown prisms share a rough mineral root instead of floating as separate gems.
  base=np.array(src['verts']);base-=base.mean(0);base/=np.linalg.norm(base,axis=1).max();base*=np.array([.4,.36,.16]);base[:,2]-=.22
  # Subdivided irregular mineral matrix, no unbroken polygonal pedestal.
  bv=base.tolist();bf=[]
  for face in src['faces']:
   for j in range(1,len(face)-1):
    tri=[face[0],face[j],face[j+1]];mid=np.mean(base[tri],axis=0)+rng.normal(0,.026,3);idx=len(bv);bv.append(mid.tolist());bf.extend([(tri[k],tri[(k+1)%3],idx) for k in range(3)])
  add(bv,bf,2)
  for prism in range(int(rng.integers(4,8))):
   radius=rng.uniform(.13,.23);length=rng.uniform(.65,1.25);center=rng.normal(0,.2,3);center[2]=-.2;tilt=rng.normal(0,.3,3);tilt[2]=1;tilt/=np.linalg.norm(tilt);u=np.cross(tilt,[0,1,0]);u/=np.linalg.norm(u);v=np.cross(tilt,u);vv=[center+tilt*z+radius*(math.cos(a)*u+math.sin(a)*v) for z in [0,length*.75] for a in np.linspace(0,math.tau,6,endpoint=False)]+[center+tilt*length];fa=[tuple(range(5,-1,-1))]+[(j,(j+1)%6,(j+1)%6+6,j+6) for j in range(6)]+[(12,j+6,(j+1)%6+6) for j in range(6)];add(vv,fa,0 if prism%3 else 1)
  verts=np.array(verts);verts-=verts.mean(0);verts/=np.linalg.norm(verts,axis=1).max();verts=verts.tolist()
 layers.append({'verts':verts,'faces':faces,'materials':mi})
# A studio environment is visible through the refractive pieces, while camera rays see black.
w=s.world;w.use_nodes=True;n=w.node_tree.nodes;n.clear();l=w.node_tree.links;wo=n.new('ShaderNodeOutputWorld');mix=n.new('ShaderNodeMixShader');ray=n.new('ShaderNodeLightPath');env=n.new('ShaderNodeBackground');env.inputs['Color'].default_value=(.18,.26,.32,1);env.inputs['Strength'].default_value=.6;black=n.new('ShaderNodeBackground');black.inputs['Color'].default_value=(0,0,0,1);l.new(ray.outputs['Is Camera Ray'],mix.inputs[0]);l.new(env.outputs[0],mix.inputs[1]);l.new(black.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],wo.inputs[0])
invisible=bpy.data.materials.new('Invisible collision hull');invisible.use_nodes=True;nt=invisible.node_tree;nt.nodes.clear();tr=nt.nodes.new('ShaderNodeBsdfTransparent');mo=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(tr.outputs[0],mo.inputs['Surface'])
births=[];spawned=[]
pieceCount=240 if KIND in ['ice','glass'] else 96
for k in range(pieceCount):
 b=4+int(k*47/pieceCount);t=(b-1)/30;p,d,on,speed=pose(t);r=random.uniform(.14,.24) if (k%4==0 or KIND=='crystal') else random.uniform(.022,.065);a=random.random()*math.tau;offset=random.random()**.5*.18
 center=Vector((float(p[0]-d[1]*math.cos(a)*offset),math.sin(a)*offset,float(p[1]+d[0]*math.cos(a)*offset)));vel=Vector((float(d[0])*1.6,random.uniform(-.14,.14),float(d[1])*1.6))
 # Reject overlaps at emission instead of letting Bullet explosively separate intersecting stones.
 for attempt in range(100):
  angle=random.random()*math.tau;cross=random.random()**.5*.25;along=random.uniform(-.055,.055)
  candidate=Vector((float(p[0]-d[1]*math.cos(angle)*cross+d[0]*along),math.sin(angle)*cross,float(p[1]+d[0]*math.cos(angle)*cross+d[1]*along)))
  clear=True
  for ot,op,ov,orr in spawned:
   age=t-ot
   if age>1.2:continue
   predicted=op+ov*age+Vector((0,0,-.25*age*age))
   if (candidate-predicted).length<r+orr+.006:clear=False;break
  if clear:break
  if attempt in [35,65,85]:r*=.85
 center=candidate;spawned.append((t,center.copy(),vel.copy(),r))
 src=data['pieces'][k%len(data['pieces'])];vs=[Vector(v) for v in src['verts']];centroid=sum(vs,Vector())/len(vs);radius=max((v-centroid).length for v in vs);vs=[(v-centroid)*(r/radius) for v in vs]
 vs=[Vector(v)*r for v in layers[k%len(layers)]['verts']];me=bpy.data.meshes.new('Convex stone');me.from_pydata(vs,[],layers[k%len(layers)]['faces']);me.update();o=bpy.data.objects.new('Emitted stone '+str(k),me);bpy.context.collection.objects.link(o);o.data.materials.append(mats[k%len(mats)]);bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.rigidbody.object_add();o.select_set(False);rb=o.rigid_body;rb.mass=max(.01,src['volume']*(r/radius)**3*2700);rb.collision_shape='CONVEX_HULL';rb.use_margin=True;rb.collision_margin=.001;rb.friction=.68;rb.restitution=.04;rb.linear_damping=.12;rb.angular_damping=.08
 o.location=(50+k*.5,0,-10);o.keyframe_insert('location',frame=1);o.hide_render=True;o.keyframe_insert('hide_render',frame=1);o.keyframe_insert('hide_render',frame=b-2)
 o.location=center-vel/30;o.keyframe_insert('location',frame=b-1);o.hide_render=False;o.keyframe_insert('hide_render',frame=b-1);o.location=center;o.keyframe_insert('location',frame=b)
 o.rotation_euler=[random.random()*6 for _ in range(3)];o.keyframe_insert('rotation_euler',frame=b-1);o.rotation_euler.rotate_axis('Y',random.uniform(-.08,.08));o.keyframe_insert('rotation_euler',frame=b)
 rb.kinematic=True;rb.keyframe_insert('kinematic',frame=1);rb.keyframe_insert('kinematic',frame=b);rb.kinematic=False;rb.keyframe_insert('kinematic',frame=b+1)
 for fc in o.animation_data.action.fcurves:
  for key in fc.keyframe_points:key.interpolation='CONSTANT' if fc.data_path in ['hide_render','rigid_body.kinematic'] else 'LINEAR'
 # Render a layered, eroded surface within the unchanged convex collision hull.
 me.materials.clear();me.materials.append(invisible)
 # Collision geometry must not consume transparent ray bounces or shadow the optical child.
 for visibility in ['visible_camera','visible_diffuse','visible_glossy','visible_transmission','visible_shadow','visible_volume_scatter']:setattr(o,visibility,False)
 family=k%len(layers)
 if family not in layerMeshes:
  surface=layers[family];lm=bpy.data.meshes.new('Layered fracture '+str(family));lm.from_pydata(surface['verts'],[],surface['faces']);lm.update()
  for mat in rockMats:lm.materials.append(mat)
  for face,idx in zip(lm.polygons,surface['materials']):face.material_index=idx;face.use_smooth=False
  bm=bmesh.new();bm.from_mesh(lm);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(lm);bm.free();layerMeshes[family]=lm
 child=bpy.data.objects.new('Layered stone '+str(k),layerMeshes[family]);bpy.context.collection.objects.link(child);child.parent=o;child.scale=(r,r,r);child.hide_render=True;child.keyframe_insert('hide_render',frame=1);child.keyframe_insert('hide_render',frame=b-2);child.hide_render=False;child.keyframe_insert('hide_render',frame=b-1)
 if KIND in ['ice','glass']:
  bevel=child.modifiers.new('Caught fracture edges','BEVEL');bevel.width=.012 if KIND=='ice' else .004;bevel.segments=3
 births.append({'frame':b,'source':p.tolist(),'center':list(center),'velocity':list(vel),'radius':r})
s.rigidbody_world.substeps_per_frame=8;s.rigidbody_world.solver_iterations=20;s.rigidbody_world.point_cache.frame_end=120
for name,loc,power,size in [('Key',(-2,-4,3.8),350,3),('Rim',(1,2,4),500,4)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler()
if KIND=='crystal':
 env.inputs['Strength'].default_value=1.8
 d=bpy.data.lights.new('Broad frontal fill','AREA');d.energy=550;d.shape='DISK';d.size=7;o=bpy.data.objects.new('Broad frontal fill',d);bpy.context.collection.objects.link(o);o.location=(0,-4,2.5);o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-15,DATA['camera']['center'][1]));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,DATA['camera']['center'][1]))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=DATA['camera']['width'];s.camera=cam
full='--full' in sys.argv;start=time.time()
for f in range(1,121):
 s.frame_set(f)
 if full or f in [41,61]:s.render.filepath=str(out/f'{f-1:04}.jpg');bpy.ops.render.render(write_still=True)
 if f==41 and not full:
  cam.data.ortho_scale=3.8;cam.location.x=.8;cam.location.z=1.7;s.render.filepath=str(R/'subelements'/f'photo-{KIND}-close.jpg');bpy.ops.render.render(write_still=True);cam.data.ortho_scale=10.5;cam.location.x=0;cam.location.z=1.903125
 if f%15==0:print('FRAME',f,'seconds',round(time.time()-start,1),flush=True)
(R/'subelements'/f'photo-{KIND}-report.json').write_text(json.dumps({'births':births,'frames':120,'fps':30,'trail':'shared-trail.json','lift':'Effective gravity .5 m/s2 during drawing, ramp to 9.81 after frame 51; Bullet free release and contacts','camera':DATA['camera']}))
