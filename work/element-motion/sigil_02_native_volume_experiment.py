"""Cycles material studies, native Bullet release, CPU-solved local gas.
The powered assembly is authored. Ice and basalt are rigid fractures, not a
thermodynamic phase-change/viscoelastic lava solver. Electrical channels are
an authored branching discharge visualization, not calibrated plasma.
"""
import bpy,math,json,sys,time,random
import numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion,Euler
R=Path(__file__).resolve().parent;args=sys.argv[sys.argv.index('--')+1:];kind=args[0];full='--full' in args
O=R/'sigil-02-active-elements'/kind;out=O/('eevee-check' if '--eevee-check' in args else 'volume-fast-check' if '--volume-check' in args else 'frames' if full else 'pilot');out.mkdir(parents=True,exist_ok=True)
selected=[30,66,102,150,192,228,258,294]
if '--motion' in args:selected=list(range(0,300,10))
if '--single' in args:selected=[150]
if '--release-check' in args:selected=[228,258,294]
if '--volume-check' in args:selected=[150]
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.device='GPU' if full else 'CPU';s.cycles.samples=64 if full else 12;s.cycles.use_denoising=True;s.cycles.adaptive_threshold=.018;s.cycles.max_bounces=12;s.cycles.transmission_bounces=10;s.cycles.volume_bounces=2;s.cycles.volume_step_rate=3.0;s.render.use_persistent_data=True;s.render.threads_mode='FIXED';s.render.threads=2;s.render.resolution_x=1920 if full else 768;s.render.resolution_y=1080 if full else 432;s.render.resolution_percentage=100;s.render.fps=30;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=97;s.view_settings.view_transform='AgX';s.frame_end=300
if full:
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
 for d in prefs.devices:d.use=d.type=='OPTIX'
if '--eevee-check' in args:
 s.render.engine='CYCLES' if kind!='lightning' else 'BLENDER_EEVEE_NEXT'
 if kind=='lightning':
  s.eevee.taa_render_samples=96;s.eevee.volumetric_tile_size='2';s.eevee.volumetric_samples=128;s.eevee.use_volumetric_shadows=True
 s.render.use_persistent_data=False
s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=0
bpy.ops.object.camera_add(location=(.25,-17.2,5.1));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1.55))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=48;cam.data.sensor_width=36;s.camera=cam
def material(name,color,roughness):
 m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=roughness;return m,p
def light(name,loc,power,color,size=3,point=False):
 d=bpy.data.lights.new(name,'POINT' if point else 'AREA');d.energy=power;d.color=color
 if point:d.shadow_soft_size=.1
 else:d.shape='DISK';d.size=size
 o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler();return o
def noise_bump(m,scale,amount,distance):
 n=m.node_tree.nodes;l=m.node_tree.links;no=n.new('ShaderNodeTexNoise');no.inputs['Scale'].default_value=scale;no.inputs['Detail'].default_value=5;no.inputs['Roughness'].default_value=.75;bu=n.new('ShaderNodeBump');bu.inputs['Strength'].default_value=amount;bu.inputs['Distance'].default_value=distance;l.new(no.outputs['Fac'],bu.inputs['Height']);l.new(bu.outputs['Normal'],n.get('Principled BSDF').inputs['Normal']);return no
def smooth(x):x=max(0,min(1,x));return x*x*(3-2*x)
objects=[];heat=[];crusts=[]
if kind!='lightning':
 fm,fp=material('Black contact stage',(0,0,0),1);fp.inputs['Specular IOR Level'].default_value=0
 bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,-.10));floor=bpy.context.object;floor.scale=(40,40,.20);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);floor.hide_render=True;bpy.ops.rigidbody.object_add();floor.rigid_body.type='PASSIVE';floor.rigid_body.friction=.84
 bpy.ops.mesh.primitive_plane_add(size=40);bpy.context.object.data.materials.append(fm)
 data=json.loads((R/'sigil-02-coherent/earth-geometry.json').read_text())
 if kind=='ice':
  m,p=material('Glacial ice / clear core with frosted microfractures',(.995,.999,1),.04);p.inputs['Transmission Weight'].default_value=1;p.inputs['IOR'].default_value=1.31
  n=m.node_tree.nodes;l=m.node_tree.links;no=noise_bump(m,52,.20,.004)
  rem=n.new('ShaderNodeMapRange');rem.inputs['From Min'].default_value=.38;rem.inputs['From Max'].default_value=.72;rem.inputs['To Min'].default_value=.018;rem.inputs['To Max'].default_value=.19;l.new(no.outputs['Fac'],rem.inputs['Value']);l.new(rem.outputs[0],p.inputs['Roughness'])
  ab=n.new('ShaderNodeVolumeAbsorption');ab.inputs['Color'].default_value=(.55,.80,.90,1);ab.inputs['Density'].default_value=.12
  sc=n.new('ShaderNodeVolumeScatter');sc.inputs['Color'].default_value=(.7,.88,1,1);sc.inputs['Density'].default_value=.055
  add=n.new('ShaderNodeAddShader');l.new(ab.outputs[0],add.inputs[0]);l.new(sc.outputs[0],add.inputs[1]);l.new(add.outputs[0],n.get('Material Output').inputs['Volume'])
  side=m.copy();side.name='Frosted fresh ice fracture';side.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.24
  # Reflection cards are seen through the ice, while camera rays remain black.
  wn=s.world.node_tree.nodes;wl=s.world.node_tree.links;bg=wn.get('Background');bg.inputs['Color'].default_value=(.11,.19,.26,1);bg.inputs['Strength'].default_value=.45
  black=wn.new('ShaderNodeBackground');black.inputs['Strength'].default_value=0;lp=wn.new('ShaderNodeLightPath');mix=wn.new('ShaderNodeMixShader');wl.new(lp.outputs['Is Camera Ray'],mix.inputs[0]);wl.new(bg.outputs[0],mix.inputs[1]);wl.new(black.outputs[0],mix.inputs[2]);wl.new(mix.outputs[0],wn.get('World Output').inputs['Surface'])
  camdiff=wn.new('ShaderNodeMath');camdiff.operation='MAXIMUM';wl.new(lp.outputs['Is Camera Ray'],camdiff.inputs[0]);wl.new(lp.outputs['Is Diffuse Ray'],camdiff.inputs[1]);wl.new(camdiff.outputs[0],mix.inputs[0])
  tc=wn.new('ShaderNodeTexCoord');sp=wn.new('ShaderNodeSeparateXYZ');wl.new(tc.outputs['Normal'],sp.inputs[0]);ra=wn.new('ShaderNodeValToRGB');ra.color_ramp.elements[0].position=.0;ra.color_ramp.elements[0].color=(.025,.035,.04,1);ra.color_ramp.elements[1].position=.5;ra.color_ramp.elements[1].color=(.65,.72,.78,1);e=ra.color_ramp.elements.new(.32);e.color=(.10,.16,.21,1);wl.new(sp.outputs['Z'],ra.inputs[0]);wl.new(ra.outputs[0],bg.inputs['Color'])
  light('Broad glacial key',(-3,-4,6),500,(.55,.78,1),5);light('Transmitted rim',(3,1.5,3.8),850,(.65,.85,1),3);light('Fine white edge',(-4,2,3),650,(1,1,1),2)
 else:
  m,p=material('Basalt / porous cooled crust',(.015,.012,.011),.88);no=noise_bump(m,58,.8,.017)
  n=m.node_tree.nodes;l=m.node_tree.links
  tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(next((R/'sigil-02-repair/scans/rock_09').rglob('rock_09_diff_2k.jpg'))));tex.projection='BOX';tex.projection_blend=.2
  coord=n.new('ShaderNodeTexCoord');l.new(coord.outputs['UV'],tex.inputs['Vector']);tex.projection='FLAT';nt=n.new('ShaderNodeTexImage');nt.image=bpy.data.images.load(str(next((R/'sigil-02-repair/scans/rock_09').rglob('rock_09_nor_gl_2k.jpg'))));nt.image.colorspace_settings.name='Non-Color';nm=n.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=1.1;l.new(nt.outputs[0],nm.inputs['Color']);l.new(nm.outputs[0],p.inputs['Normal']);tint=n.new('ShaderNodeMixRGB');tint.blend_type='MULTIPLY';tint.inputs[0].default_value=1;tint.inputs[2].default_value=(.48,.43,.39,1);l.new(tex.outputs[0],tint.inputs[1]);l.new(tint.outputs[0],p.inputs['Base Color']);side=m
  light('Dim neutral rim',(-2,2,5),650,(.65,.72,.8),4);light('Crust reflection',(-3,-5,5),700,(1,.78,.61),5)
 for row in data['pieces']:
  k=row['seed'];me=bpy.data.meshes.new('02 interlocking fracture');me.from_pydata(row['verts'],[],row['faces']);me.update();o=bpy.data.objects.new(f'{kind} fracture {k}',me);bpy.context.collection.objects.link(o);me.materials.append(m);me.materials.append(side);center=Vector(row['center'])
  uv=me.uv_layers.new(name='Continuous material coordinates')
  for poly in me.polygons:
   for li in poly.loop_indices:
    v=me.vertices[me.loops[li].vertex_index].co+center;uv.data[li].uv=(v.x*.65,v.z*.65)
  if kind=='lava':
   for v in me.vertices:v.co.y*=2.2
  for face in me.polygons:face.material_index=0 if face.index<row['frontFaces'] else 1;face.use_smooth=kind=='ice' and face.index<row['frontFaces']*2
  bevel=o.modifiers.new('Real chipped edge', 'BEVEL');bevel.width=.011 if kind=='ice' else .006;bevel.segments=3
  if kind=='lava':
   # Hot geometry fills the actual three-dimensional gap below each crust.
   hot,hp=material(f'Molten interior {k}',(.09,.007,.001),.32);hp.inputs['Emission Color'].default_value=(1,.105,.006,1);hp.inputs['Emission Strength'].default_value=3;noise_bump(hot,10,.2,.009);heat.append((hp,k))
   core=bpy.data.objects.new(f'Hot interior {k}',me.copy());bpy.context.collection.objects.link(core);core.data.materials.clear();core.data.materials.append(hot)
   for poly in core.data.polygons:poly.material_index=0;poly.use_smooth=True
   core.parent=o;core.scale=(1.0,.65,1.0)
   for v in me.vertices:v.co*=.925+.035*math.sin(k*2.137)
   sub=o.modifiers.new('Fracture surface tessellation','SUBSURF');sub.subdivision_type='SIMPLE';sub.levels=1;sub.render_levels=1
   # Physical relief, separate from the optical micro-normal texture.
   dis=o.modifiers.new('Basalt broken relief','DISPLACE');tx=bpy.data.textures.new(f'Basalt pore {k}',type='CLOUDS');tx.noise_scale=.055;tx.noise_depth=2;dis.texture=tx;dis.strength=.028
  if kind=='ice':
   for v in me.vertices:v.co.y*=1.65
  o.location=center;bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.rigidbody.object_add();o.select_set(False);rb=o.rigid_body;rb.mass=max(.01,row['volume']*(917 if kind=='ice' else 2800));rb.collision_shape='CONVEX_HULL';rb.use_margin=True;rb.collision_margin=.001;rb.friction=.35 if kind=='ice' else .84;rb.restitution=.06 if kind=='ice' else .015;rb.linear_damping=.07;rb.angular_damping=.16
  # Shortest-arc orientation interpolation prevents the old multi-turn bug.
  initial=Euler((1.2+.35*math.sin(k),.3*math.cos(k*2),((k*2.399+math.pi)%(2*math.pi))-math.pi)).to_quaternion();identity=Quaternion();o.rotation_mode='QUATERNION'
  bottom=min((initial@v.co).z for v in me.vertices);u=(center.x+4.1)/8.2;start=Vector((center.x+.35*math.sin(k*1.73),.7*math.sin(k*2.4),-bottom+.02))
  for f in range(1,220,3):
   t=(f-1)/30;a=smooth((t-.25-.35*u)/(2.0 if kind=='ice' else 2.9));o.location=start.lerp(center,a);o.location.y+=math.sin(a*math.pi)*(.45*math.sin(u*4)+.20*math.sin(k));o.rotation_quaternion=initial.slerp(identity,a)
   stress=smooth((t-3.1)/.6)*(1-smooth((t-6.65)/.5));wave=t*.9-center.x*.75
   o.location+=Vector((.007*math.sin(wave+k*.2),(.035 if kind=='ice' else .08)*math.sin(wave+k*.17),.012*math.cos(wave+k*.12)))*stress
   o.keyframe_insert('location',frame=f);o.keyframe_insert('rotation_quaternion',frame=f)
  o.location=center;o.rotation_quaternion=identity;o.keyframe_insert('location',frame=219);o.keyframe_insert('rotation_quaternion',frame=219)
  rb.kinematic=True;rb.keyframe_insert('kinematic',frame=1);rb.keyframe_insert('kinematic',frame=219);rb.kinematic=False;rb.keyframe_insert('kinematic',frame=220)
  for fc in o.animation_data.action.fcurves:
   for key in fc.keyframe_points:key.interpolation='CONSTANT' if fc.data_path=='rigid_body.kinematic' else 'LINEAR'
  objects.append(o)
 s.rigidbody_world.substeps_per_frame=16;s.rigidbody_world.solver_iterations=40;s.rigidbody_world.point_cache.frame_end=300

# The image atlas is two adjacent slices of a solved 3D density field. It is
# sampled inside a real volume, not composited as a screen-space cloud layer.
volumeHeight=8.1 if kind=='lava' else 5.4;volumeNz=108 if kind=='lava' else 72
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,volumeHeight/2));cloud=bpy.context.object;cloud.name='CPU advected gas / path-traced volume';cloud.scale=(11,3.6,volumeHeight)
vm=bpy.data.materials.new('Solved atmosphere');vm.use_nodes=True;vn=vm.node_tree.nodes;vl=vm.node_tree.links;vn.remove(vn.get('Principled BSDF'));coord=vn.new('ShaderNodeNewGeometry');shift=vn.new('ShaderNodeVectorMath');shift.operation='SUBTRACT';shift.inputs[1].default_value=(-5.5,-1.8,0);vl.new(coord.outputs['Position'],shift.inputs[0]);normalized=vn.new('ShaderNodeVectorMath');normalized.operation='DIVIDE';normalized.inputs[1].default_value=(11,3.6,volumeHeight);vl.new(shift.outputs[0],normalized.inputs[0]);sep=vn.new('ShaderNodeSeparateXYZ');vl.new(normalized.outputs[0],sep.inputs[0])
def op(operation,a,b=None):
 no=vn.new('ShaderNodeMath');no.operation=operation
 for i,value in enumerate([a,b]):
  if value is None:continue
  if isinstance(value,(float,int)):no.inputs[i].default_value=value
  else:vl.new(value,no.inputs[i])
 return no.outputs[0]
layer=op('MULTIPLY',sep.outputs['Y'],35);index=op('FLOOR',layer);frac=op('FRACT',layer);images=[]
for offset in [0,1]:
 ix=op('MINIMUM',op('ADD',index,offset),35);col=op('MODULO',ix,6);row=op('FLOOR',op('DIVIDE',ix,6));u=op('DIVIDE',op('ADD',op('ADD',op('MULTIPLY',sep.outputs['X'],111),.5),op('MULTIPLY',col,112)),672);v=op('DIVIDE',op('ADD',op('ADD',op('MULTIPLY',sep.outputs['Z'],volumeNz-1),.5),op('MULTIPLY',row,volumeNz)),volumeNz*6)
 combine=vn.new('ShaderNodeCombineXYZ');vl.new(u,combine.inputs['X']);vl.new(v,combine.inputs['Y']);im=vn.new('ShaderNodeTexImage');im.interpolation='Linear';im.extension='CLIP';vl.new(combine.outputs[0],im.inputs['Vector']);images.append(im)
blend=vn.new('ShaderNodeMixRGB');vl.new(frac,blend.inputs[0]);vl.new(images[0].outputs['Color'],blend.inputs[1]);vl.new(images[1].outputs['Color'],blend.inputs[2]);noise=vn.new('ShaderNodeTexNoise');noise.noise_dimensions='4D';noise.inputs['Scale'].default_value=32;noise.inputs['Detail'].default_value=5;noise.inputs['Roughness'].default_value=.8;vl.new(normalized.outputs[0],noise.inputs['Vector']);density=op('MULTIPLY',blend.outputs[0],noise.outputs['Fac']);density=op('MULTIPLY',density,{'lightning':3.0,'lava':1.4,'ice':.30}[kind]);volume=vn.new('ShaderNodeVolumePrincipled');volume.inputs['Color'].default_value=(.47,.55,.68,1) if kind=='lightning' else (.65,.76,.8,1) if kind=='ice' else (.23,.20,.18,1);volume.inputs['Anisotropy'].default_value=.2;vl.new(density,volume.inputs['Density']);vl.new(volume.outputs[0],vn.get('Material Output').inputs['Volume']);cloud.data.materials.append(vm)

# Native OpenVDB geometry replaces repeated texture-atlas ray sampling.
# All original density cells, including empty cells, are retained.
shape=(112,36,volumeNz);vmin=np.array([-5.5,-1.8,0.]);vextent=np.array([11.,3.6,volumeHeight]);spacing=vextent/np.array(shape)
xyz=np.indices(shape,dtype=np.float32).reshape(3,-1).T*spacing+vmin+spacing*.5
oldCube=cloud.data;gridMesh=bpy.data.meshes.new('Advected density samples');gridMesh.from_pydata(xyz.tolist(),[],[]);gridMesh.update();densityAttr=gridMesh.attributes.new('gas_density','FLOAT','POINT');cloud.data=gridMesh;cloud.location=(0,0,0);cloud.scale=(1,1,1);gridMesh.materials.append(vm);bpy.data.meshes.remove(oldCube)
ng=bpy.data.node_groups.new('Native volume from exact CPU density samples','GeometryNodeTree');ng.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');ng.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry');gn=ng.nodes;glink=ng.links;gi=gn.new('NodeGroupInput');go=gn.new('NodeGroupOutput');nearest=gn.new('GeometryNodeSampleNearest');nearest.domain='POINT';glink.new(gi.outputs['Geometry'],nearest.inputs['Geometry']);sample=gn.new('GeometryNodeSampleIndex');sample.data_type='FLOAT';sample.domain='POINT';glink.new(gi.outputs['Geometry'],sample.inputs['Geometry']);named=gn.new('GeometryNodeInputNamedAttribute');named.data_type='FLOAT';named.inputs['Name'].default_value='gas_density';glink.new(named.outputs['Attribute'],sample.inputs['Value']);glink.new(nearest.outputs['Index'],sample.inputs['Index']);cube=gn.new('GeometryNodeVolumeCube');cube.inputs['Min'].default_value=tuple(vmin+spacing*.5);cube.inputs['Max'].default_value=tuple(vmin+vextent-spacing*.5)
for axis,nres in zip(['X','Y','Z'],shape):cube.inputs['Resolution '+axis].default_value=nres*2
gpos=gn.new('GeometryNodeInputPosition');gshift=gn.new('ShaderNodeVectorMath');gshift.operation='SUBTRACT';gshift.inputs[1].default_value=tuple(vmin);glink.new(gpos.outputs[0],gshift.inputs[0]);gscale=gn.new('ShaderNodeVectorMath');gscale.operation='DIVIDE';gscale.inputs[1].default_value=tuple(vextent);glink.new(gshift.outputs[0],gscale.inputs[0]);gnoise=gn.new('ShaderNodeTexNoise');gnoise.noise_dimensions='4D';gnoise.inputs['Scale'].default_value=32;gnoise.inputs['Detail'].default_value=5;gnoise.inputs['Roughness'].default_value=.8;glink.new(gscale.outputs[0],gnoise.inputs['Vector']);gd=gn.new('ShaderNodeMath');gd.operation='MULTIPLY';glink.new(sample.outputs['Value'],gd.inputs[0]);glink.new(gnoise.outputs['Fac'],gd.inputs[1]);glink.new(gd.outputs[0],cube.inputs['Density']);setmat=gn.new('GeometryNodeSetMaterial');setmat.inputs['Material'].default_value=vm;glink.new(cube.outputs['Volume'],setmat.inputs['Geometry']);glink.new(setmat.outputs['Geometry'],go.inputs['Geometry']);mod=cloud.modifiers.new('Sparse 3D density grid','NODES');mod.node_group=ng
attribute=vn.new('ShaderNodeAttribute');attribute.attribute_name='density';nativeDensity=op('MULTIPLY',attribute.outputs['Fac'],{'lightning':3.0,'lava':1.4,'ice':.30}[kind]);vl.new(nativeDensity,volume.inputs['Density'])
electric=[];lamps=[]
if kind=='lightning':
 families=json.loads((O/'channels.json').read_text())['families']
 for family,paths in enumerate(families):
  for group in range(6):
   cu=bpy.data.curves.new('Branched discharge','CURVE');cu.dimensions='3D';cu.resolution_u=1;cu.bevel_depth=.004;cu.bevel_resolution=2
   for path in paths:
    if path['group']!=group:continue
    sp=cu.splines.new('POLY');sp.points.add(len(path['points'])-1)
    for i,(p,xyz) in enumerate(zip(sp.points,path['points'])):p.co=(*xyz,1);p.radius=path['radius']/.004*(1 if path['power']>.4 else max(.12,1-i/len(sp.points)))
   em=bpy.data.materials.new('Ionized channel');em.use_nodes=True;em.cycles.emission_sampling='NONE';n=em.node_tree.nodes;n.clear();node=n.new('ShaderNodeEmission');node.inputs['Color'].default_value=(.52,.70,1,1);node.inputs['Strength'].default_value=40;output=n.new('ShaderNodeOutputMaterial');em.node_tree.links.new(node.outputs[0],output.inputs['Surface']);cu.materials.append(em);ob=bpy.data.objects.new(f'Channel {family}/{group}',cu);bpy.context.collection.objects.link(ob);electric.append((ob,node,family,group))
 for g in range(6):lamps.append(light(f'In-cloud discharge {g}',(-3.4+g*1.35,.12,1.75+.25*math.sin(g)),20,(.34,.50,1),point=True))
elif kind=='lava':
 for g in range(6):lamps.append(light(f'Molten bounce {g}',(-3.4+g*1.35,-.05,1.8),10,(1,.13,.012),point=True))

s.use_nodes=True;cn=s.node_tree.nodes;cn.clear();rl=cn.new('CompositorNodeRLayers');gl=cn.new('CompositorNodeGlare');gl.glare_type='FOG_GLOW';gl.quality='HIGH';gl.threshold=1.5;gl.mix=-.9;com=cn.new('CompositorNodeComposite');s.node_tree.links.new(rl.outputs['Image'],gl.inputs['Image']);s.node_tree.links.new(gl.outputs['Image'],com.inputs[0])
old=None;rows=[];begun=time.time()
for f in range(300):
 s.frame_set(f+1);t=f/30
 if kind!='lightning':
  retreat=smooth((t-7.0)/2.3);cam.location=(.25,-17.2-3.2*retreat,5.1+.4*retreat);cam.rotation_euler=(Vector((0,0,1.45))-cam.location).to_track_quat('-Z','Y').to_euler()
 if f%30==0 and objects:
  dg=bpy.context.evaluated_depsgraph_get();poses=[o.evaluated_get(dg).matrix_world.translation for o in objects];rows.append(dict(frame=f,finite=all(all(math.isfinite(x) for x in p) for p in poses),nearFloor=sum(p.z<.5 for p in poses)))
 if (not full or '--volume-check' in args) and f not in selected:continue
 if (out/f'{f:04}.jpg').exists():continue
 if old:
  for im in images:im.image=None
  bpy.data.images.remove(old)
 path=O/'density'/f'{f:04}.png'
 while not path.exists():time.sleep(.3)
 old=bpy.data.images.load(str(path));old.colorspace_settings.name='Non-Color'
 for im in images:im.image=old
 pixels=np.empty(len(old.pixels),np.float32);old.pixels.foreach_get(pixels);atlas=pixels.reshape(volumeNz*6,672,4)[:,:,0];rho=np.empty(shape,np.float32)
 for layerIndex in range(36):rho[:,layerIndex,:]=atlas[(layerIndex//6)*volumeNz:(layerIndex//6+1)*volumeNz,(layerIndex%6)*112:(layerIndex%6+1)*112].T
 densityAttr.data.foreach_set('value',rho.ravel());gridMesh.update();cloud.update_tag()
 noise.inputs['W'].default_value=t*.035;gnoise.inputs['W'].default_value=t*.035
 if kind=='lightning':
  envelope=smooth((t-.1)/1.9)*(1-smooth((t-7.5)/1.0))
  energies=[]
  for g in range(6):
   local=t*4.7+g*.379;phase=local%1;power=(.015+2.2*math.exp(-((phase-.13)/.12)**2)+.9*math.exp(-((phase-.48)/.10)**2))*envelope;energies.append(power);lamps[g].data.energy=power*12
  for ob,node,family,g in electric:
   current=int(t*4.7+g*.379)%len(families);ob.hide_render=family not in [current,(current+2)%len(families)];node.inputs['Strength'].default_value=energies[g]*120*(1 if family==current else .12)
 if kind=='lava':
  cooling=1-.65*smooth((t-5.5)/4)
  for hp,k in heat:hp.inputs['Emission Strength'].default_value=(1.8+1.4*(.5+.5*math.sin(t*.6+k*2.1))**3)*cooling
  for lamp in lamps:lamp.data.energy=10*cooling*(1-smooth((t-7.2)/1.8))
 s.render.use_motion_blur=kind!='lightning';s.render.motion_blur_shutter=.32
 s.render.filepath=str(out/f'{f:04}.jpg');bpy.ops.render.render(write_still=True);print(kind,'FRAME',f,'seconds',round(time.time()-begun),flush=True)
(O/('render-report.json' if full else 'cpu-report.json')).write_text(json.dumps(dict(element=kind,frames=300,rendered=300 if full else selected,resolution=[s.render.resolution_x,s.render.resolution_y],samples=s.cycles.samples,method=__doc__,rows=rows,userAccepted=False),indent=2));print('COMPLETE',flush=True)
