import bpy,json,gzip,struct,sys,time
from pathlib import Path
import numpy as np
from mathutils import Vector
R=Path(__file__).resolve().parent;full='--full' in sys.argv;O=R/'sigil-02-active-elements'/('water-full' if full else 'water-cpu');cache=O/('preview-mesh' if '--preview' in sys.argv else 'mesh');out=O/('frames' if full else 'preview-frames' if '--preview' in sys.argv else 'pilot');out.mkdir(exist_ok=True)
while not (cache/'manifest.json').exists():time.sleep(.5)
manifest=json.loads((cache/'manifest.json').read_text())
s=bpy.context.scene;bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);s.render.engine='CYCLES';s.cycles.device='GPU' if '--full' in sys.argv else 'CPU';s.cycles.samples=96 if '--full' in sys.argv else 12;s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.adaptive_threshold=.012;s.cycles.max_bounces=12;s.cycles.transmission_bounces=10;s.cycles.glossy_bounces=6;s.cycles.diffuse_bounces=2;s.cycles.caustics_reflective=False;s.cycles.caustics_refractive=False;s.render.use_persistent_data=True;s.render.threads_mode='FIXED';s.render.threads=3;s.render.resolution_x=1920 if '--full' in sys.argv else 768;s.render.resolution_y=1080 if '--full' in sys.argv else 432;s.render.resolution_percentage=100;s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=97;s.view_settings.view_transform='AgX'
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
# Black camera background; studio illumination is configured below.
w=s.world;w.use_nodes=True;w.node_tree.nodes.get('Background').inputs['Color'].default_value=(0,0,0,1);w.node_tree.nodes.get('Background').inputs['Strength'].default_value=0
# Studio illumination visible in reflection/refraction; the camera sees pure black.
wn=w.node_tree.nodes;wl=w.node_tree.links;bg=wn.get('Background');bg.inputs['Strength'].default_value=.6
geo=wn.new('ShaderNodeTexCoord');sep=wn.new('ShaderNodeSeparateXYZ');wl.new(geo.outputs['Normal'],sep.inputs[0])
ramp=wn.new('ShaderNodeValToRGB');cr=ramp.color_ramp;cr.elements.remove(cr.elements[1]);cr.elements[0].position=0;cr.elements[0].color=(.045,.11,.18,1)
for position,color in [(.30,(.12,.24,.36,1)),(.65,(.035,.08,.14,1)),(1.,(.30,.50,.66,1))]:
 e=cr.elements.new(position);e.color=color
wl.new(sep.outputs['Z'],ramp.inputs[0]);wl.new(ramp.outputs[0],bg.inputs['Color'])
black=wn.new('ShaderNodeBackground');black.inputs['Color'].default_value=(0,0,0,1);black.inputs['Strength'].default_value=0
lp=wn.new('ShaderNodeLightPath');mix=wn.new('ShaderNodeMixShader');wl.new(lp.outputs['Is Camera Ray'],mix.inputs[0]);wl.new(bg.outputs[0],mix.inputs[1]);wl.new(black.outputs[0],mix.inputs[2]);wl.new(mix.outputs[0],wn.get('World Output').inputs['Surface'])
m=bpy.data.materials.new('Clear water / optical transport');m.use_nodes=True;n=m.node_tree.nodes;p=n.get('Principled BSDF');p.inputs['Base Color'].default_value=(.995,.999,1,1);p.inputs['Roughness'].default_value=.006;p.inputs['IOR'].default_value=1.333;p.inputs['Transmission Weight'].default_value=1;absorb=n.new('ShaderNodeVolumeAbsorption');absorb.inputs['Color'].default_value=(.24,.65,.72,1);absorb.inputs['Density'].default_value=.14;m.node_tree.links.new(absorb.outputs[0],n.get('Material Output').inputs['Volume'])
# Unresolved capillary-wave normal detail. Deep-water capillary dispersion:
# omega^2 = sigma/rho * k^3 in native meters, with the simulation's time scale.
# It changes optical normals only; the resolved silhouette stays native FLIP.
links=m.node_tree.links;position=n.new('ShaderNodeNewGeometry');wave_phases=[];height=None
for j,wavelength in enumerate([.045,.059,.077,.10,.13,.17,.22,.29]):
 angle=j*2.399963;direction=np.array([np.cos(angle),.23*np.sin(angle*.71),np.sin(angle)]);direction/=np.linalg.norm(direction);k=2*np.pi/wavelength
 dot=n.new('ShaderNodeVectorMath');dot.operation='DOT_PRODUCT';dot.inputs[1].default_value=tuple(direction*k);links.new(position.outputs['Position'],dot.inputs[0])
 phase=n.new('ShaderNodeMath');phase.operation='ADD';links.new(dot.outputs['Value'],phase.inputs[0]);wave_phases.append((phase,float(np.sqrt(.072/1000*(k/.35)**3)*.4),j*1.731))
 sine=n.new('ShaderNodeMath');sine.operation='SINE';links.new(phase.outputs[0],sine.inputs[0]);amp=n.new('ShaderNodeMath');amp.operation='MULTIPLY';amp.inputs[1].default_value=.00045*(wavelength/.10)**.65;links.new(sine.outputs[0],amp.inputs[0])
 if height is None:height=amp.outputs[0]
 else:
  add=n.new('ShaderNodeMath');add.operation='ADD';links.new(height,add.inputs[0]);links.new(amp.outputs[0],add.inputs[1]);height=add.outputs[0]
bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.9;bump.inputs['Distance'].default_value=1;links.new(height,bump.inputs['Height']);links.new(bump.outputs['Normal'],p.inputs['Normal'])
for name,loc,power,size,sy in [('Long white strip',(-2,-2,5.8),520,5.5,.75),('Edge card',(4,1.4,2.5),800,1.4,4.5),('Soft rim',(-4,2,3.6),850,3.8,2.3),('Low bounce',(-1,-1,-1.3),80,4,.9),('Broad front card',(1,-4,3.4),95,4.6,3.2)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.color=(.70,.85,1.0) if name=='Broad front card' else (1,1,1);d.shape='RECTANGLE';d.size=size;d.size_y=sy;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.8))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(.25,-17.2,5.1));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1.55))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='PERSP';cam.data.lens=48;cam.data.sensor_width=36;s.camera=cam
# Broad studio illumination supplies a visible refracted body. Camera-ray
# visibility keeps the backdrop black; no diffuse tint or emission is added.
bg.inputs['Strength'].default_value=.48
for light in bpy.data.lights:
 light.energy*=.11
 light.color=(.18,.52,1.)

# A real opaque stage floor matches the native solid collider exactly.
bpy.ops.mesh.primitive_plane_add(size=40,location=(0,0,0));floor=bpy.context.object;floor.name='Ground / matches FLIP collider'
fm=bpy.data.materials.new('Black ground / contact');fm.use_nodes=True;fp=fm.node_tree.nodes.get('Principled BSDF');fp.inputs['Base Color'].default_value=(.012,.012,.012,1);fp.inputs['Roughness'].default_value=.65;fp.inputs['Specular IOR Level'].default_value=.012;floor.data.materials.append(fm)
# Studio environment illuminates transmissive water, but not the matte stage.
camera_or_diffuse=wn.new('ShaderNodeMath');camera_or_diffuse.operation='MAXIMUM';wl.new(lp.outputs['Is Camera Ray'],camera_or_diffuse.inputs[0]);wl.new(lp.outputs['Is Diffuse Ray'],camera_or_diffuse.inputs[1]);wl.new(camera_or_diffuse.outputs[0],mix.inputs[0])

bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1);temp=bpy.context.object;iv=np.array([list(v.co) for v in temp.data.vertices]);ifa=np.array([list(p.vertices) for p in temp.data.polygons]);bpy.data.objects.remove(temp,do_unlink=True)
origin=np.array(manifest['origin']);scale=manifest['spaceScale']
def coords(p):return np.column_stack(((p[:,0]-origin[0])/scale,(p[:,2]-origin[2])/scale,(p[:,1]-origin[1])/scale))
pointGroup=bpy.data.node_groups.new('Analytic water droplet cloud','GeometryNodeTree')
pointGroup.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');pointGroup.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
gin=pointGroup.nodes.new('NodeGroupInput');gout=pointGroup.nodes.new('NodeGroupOutput');points=pointGroup.nodes.new('GeometryNodeMeshToPoints');points.mode='VERTICES';rad=pointGroup.nodes.new('GeometryNodeInputNamedAttribute');rad.data_type='FLOAT';rad.inputs['Name'].default_value='droplet_radius';mat=pointGroup.nodes.new('GeometryNodeSetMaterial');mat.inputs['Material'].default_value=m
pointGroup.links.new(gin.outputs['Geometry'],points.inputs['Mesh']);pointGroup.links.new(rad.outputs['Attribute'],points.inputs['Radius']);pointGroup.links.new(points.outputs['Points'],mat.inputs['Geometry']);pointGroup.links.new(mat.outputs['Geometry'],gout.inputs['Geometry'])
obj=None;sprayObj=None;start=time.time();args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [];frames=range(240) if '--full' in args else list(range(0,240,6)) if '--preview' in args else [0,18,36,54,72,90,114,150,174]
if '--floor-check' in args:
 frames=[0,180,300,389];out=O/'floor-check';out.mkdir(exist_ok=True)
if '--impact-check' in args:
 frames=[270,288,300,324,354,389];out=O/'impact-final';out.mkdir(exist_ok=True)
for f in frames:
 if (out/f'{f:04}.jpg').exists():continue
 retreat=max(0,min(1,(f/30-5.8)/2.3));retreat=retreat*retreat*(3-2*retreat);cam.location=(.25,-17.2-2.0*retreat,5.1+.4*retreat);cam.rotation_euler=(Vector((0,0,1.55))-cam.location).to_track_quat('-Z','Y').to_euler()
 for phase,omega,offset in wave_phases:phase.inputs[1].default_value=offset-omega*f/30
 for previous in [obj,sprayObj]:
  if previous:
   me=previous.data;bpy.data.objects.remove(previous,do_unlink=True);bpy.data.meshes.remove(me)
 sprayObj=None
 while not (cache/f'{f:04}.mesh.gz').exists():time.sleep(.4)
 raw=gzip.decompress((cache/f'{f:04}.mesh.gz').read_bytes());nv,nf,nd=struct.unpack_from('<III',raw,4);extent=np.array(manifest['config']['extent']);off=32;verts=np.frombuffer(raw,'<u2',nv*3,off).reshape(-1,3)/65535*extent;off+=nv*6;off+=nv*6+nv;faces=np.frombuffer(raw,'<u4',nf*3,off).reshape(-1,3);off+=nf*12;drops=np.frombuffer(raw,'<u2',nd*3,off).reshape(-1,3)/65535*extent;off+=nd*6;radii=np.frombuffer(raw,'<f4',nd,off)
 vectors=np.load(cache/f'{f:04}.velocity.npz');vel=np.column_stack((vectors['surface'][:,0],vectors['surface'][:,2],vectors['surface'][:,1]))/scale*manifest['timeScale']/30;dropvel=np.column_stack((vectors['drops'][:,0],vectors['drops'][:,2],vectors['drops'][:,1]))/scale*manifest['timeScale']/30
 verts=coords(verts);faces=faces[:,[0,2,1]];droppos=coords(vectors['drop_positions'])
 if nd:
  sprayMesh=bpy.data.meshes.new('Mass-conserving spray parcels');sprayMesh.from_pydata((droppos-dropvel).tolist(),[],[]);sprayMesh.update()
  attr=sprayMesh.attributes.new('droplet_radius','FLOAT','POINT');attr.data.foreach_set('value',(radii/scale).astype(np.float32))
  sprayObj=bpy.data.objects.new('Ballistic spray',sprayMesh);bpy.context.collection.objects.link(sprayObj)
  mod=sprayObj.modifiers.new('Analytic droplet spheres','NODES');mod.node_group=pointGroup
  sprayObj.shape_key_add(name='Shutter start');key=sprayObj.shape_key_add(name='Shutter end');key.data.foreach_set('co',(droppos+dropvel).astype(np.float32).ravel());key.value=0;key.keyframe_insert(data_path='value',frame=0);key.value=1;key.keyframe_insert(data_path='value',frame=2)
  for fc in sprayMesh.shape_keys.animation_data.action.fcurves:
   for k in fc.keyframe_points:k.interpolation='LINEAR'
 me=bpy.data.meshes.new('Native FLIP surface');me.from_pydata((verts-vel).tolist(),[],faces.tolist());me.update();obj=bpy.data.objects.new('Water',me);bpy.context.collection.objects.link(obj);me.materials.append(m)
 for p in me.polygons:p.use_smooth=True
 if len(verts):
  obj.shape_key_add(name='Shutter start');key=obj.shape_key_add(name='Shutter end');key.data.foreach_set('co',(verts+vel).astype(np.float32).ravel());key.value=0;key.keyframe_insert(data_path='value',frame=0);key.value=1;key.keyframe_insert(data_path='value',frame=2)
  if me.shape_keys.animation_data and me.shape_keys.animation_data.action:
   for fc in me.shape_keys.animation_data.action.fcurves:
    for k in fc.keyframe_points:k.interpolation='LINEAR'
 s.render.use_motion_blur=True;s.render.motion_blur_shutter=.65;s.frame_set(1)
 s.render.filepath=str(out/f'{f:04}.jpg');bpy.ops.render.render(write_still=True);print('FRAME',f,round(time.time()-start,1),flush=True)
 if '--full' in args or '--preview' in args:
  vectors.close()
  for suffix in ['mesh.gz','velocity.npz']:
   exact=cache/f'{f:04}.{suffix}';assert exact.resolve().parent==cache.resolve();exact.unlink()
print('COMPLETE',flush=True)
