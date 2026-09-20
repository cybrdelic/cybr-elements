"""Cycles CPU rendering of saved continuum meshes and transported material state.

No rigid-body replay, procedurally animated shape, image generation, optical
flow, or frame interpolation. One 3D mesh and its particle-derived material
attributes is loaded for each exact simulation time. Procedural detail is fixed
in transported material coordinates and is explicitly sub-grid BSDF roughness;
it does not replace the continuum motion or claim resolved fracture topology.
"""
from __future__ import annotations
import argparse,sys,json,time,math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).parent))
from elements_core.runtime import RunIdentity,atomic_json,digest,wait_for
from elements_core.lava_material import material_controls


def parser():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--surface',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
 p.add_argument('--source',type=Path,default=Path(__file__).parent/'sigil-02-v2/source.npz')
 p.add_argument('--frames',type=int,default=60);p.add_argument('--fps',type=int,default=24)
 p.add_argument('--resolution',type=int,nargs=2,default=[960,540]);p.add_argument('--samples',type=int,default=96)
 p.add_argument('--threads',type=int,default=2);p.add_argument('--frame',type=int)
 p.add_argument('--exposure',type=float,default=.1)
 p.add_argument('--view',choices=['auto','formation','oblique','front','overhead'],default='auto')
 p.add_argument('--save-blend',action='store_true');p.add_argument('--wait-timeout',type=float,default=7200)
 return p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])


def area(name,location,power,color,size,target):
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;d.color=color
 o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=location
 o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()


def principled(name):
 m=bpy.data.materials.new(name);m.use_nodes=True
 return m,m.node_tree.nodes.get('Principled BSDF')


def attribute(nodes,name):
 node=nodes.new('ShaderNodeAttribute');node.attribute_name=name;node.label=name
 return node


def math_node(nodes,operation,a=None,b=None,label=None):
 node=nodes.new('ShaderNodeMath');node.operation=operation
 if label:node.label=label
 if a is not None:node.inputs[0].default_value=a
 if b is not None:node.inputs[1].default_value=b
 return node


def build_lava_material():
 """Finite cooled crust shell. Geometric holes, not shader cracks, expose lava."""
 lava,p=principled('Finite pahoehoe crust shell / resolved geometry')
 p.inputs['Metallic'].default_value=0.;p.inputs['IOR'].default_value=1.50
 if 'Specular IOR Level' in p.inputs:p.inputs['Specular IOR Level'].default_value=.22
 nodes=lava.node_tree.nodes;links=lava.node_tree.links
 base=attribute(nodes,'baseColor')
 rough=attribute(nodes,'roughnessBase')
 coat=attribute(nodes,'coatWeight')
 temp=attribute(nodes,'temperature')
 thermal=attribute(nodes,'thermalStrength')
 thickness=attribute(nodes,'crustThickness')
 age=attribute(nodes,'surfaceAge')
 rest=attribute(nodes,'materialCoordinates')

 macro=nodes.new('ShaderNodeTexNoise');macro.noise_dimensions='3D';macro.label='advected crust albedo breakup'
 macro.inputs['Scale'].default_value=21.;macro.inputs['Detail'].default_value=3.4
 macro.inputs['Roughness'].default_value=.66;macro.inputs['Distortion'].default_value=.12
 links.new(rest.outputs['Vector'],macro.inputs['Vector'])
 gain=nodes.new('ShaderNodeMapRange');gain.clamp=True
 gain.inputs['From Min'].default_value=.16;gain.inputs['From Max'].default_value=.84
 gain.inputs['To Min'].default_value=.68;gain.inputs['To Max'].default_value=1.18
 links.new(macro.outputs['Fac'],gain.inputs['Value'])
 albedo=nodes.new('ShaderNodeMixRGB');albedo.blend_type='MULTIPLY';albedo.inputs['Fac'].default_value=1.
 links.new(base.outputs['Color'],albedo.inputs[1]);links.new(gain.outputs['Result'],albedo.inputs[2])
 links.new(albedo.outputs['Color'],p.inputs['Base Color'])

 micro=nodes.new('ShaderNodeTexNoise');micro.noise_dimensions='3D';micro.label='crust grain and vesicle roughness'
 micro.inputs['Scale'].default_value=120.;micro.inputs['Detail'].default_value=3.0
 micro.inputs['Roughness'].default_value=.72
 links.new(rest.outputs['Vector'],micro.inputs['Vector'])
 mc=math_node(nodes,'SUBTRACT',b=.5);links.new(micro.outputs['Fac'],mc.inputs[0])
 ma=math_node(nodes,'MULTIPLY',b=.09);links.new(mc.outputs[0],ma.inputs[0])
 rt=math_node(nodes,'ADD');links.new(rough.outputs['Fac'],rt.inputs[0]);links.new(ma.outputs[0],rt.inputs[1])
 rc=nodes.new('ShaderNodeClamp');rc.inputs['Min'].default_value=.22;rc.inputs['Max'].default_value=.94
 links.new(rt.outputs[0],rc.inputs['Value']);links.new(rc.outputs['Result'],p.inputs['Roughness'])
 links.new(coat.outputs['Fac'],p.inputs['Coat Weight'])
 cr=math_node(nodes,'MULTIPLY',b=.70);links.new(rc.outputs['Result'],cr.inputs[0]);links.new(cr.outputs[0],p.inputs['Coat Roughness'])

 # Young/thin shell is translucent to thermal radiance; thick mature crust is
 # nearly opaque. The actual bright breakouts come from the separate interior.
 thin=nodes.new('ShaderNodeMapRange');thin.clamp=True;thin.interpolation_type='SMOOTHERSTEP'
 thin.inputs['From Min'].default_value=.00020;thin.inputs['From Max'].default_value=.0028
 thin.inputs['To Min'].default_value=1.;thin.inputs['To Max'].default_value=0.
 links.new(thickness.outputs['Fac'],thin.inputs['Value'])
 young=nodes.new('ShaderNodeMapRange');young.clamp=True;young.interpolation_type='SMOOTHERSTEP'
 young.inputs['From Min'].default_value=.05;young.inputs['From Max'].default_value=.85
 young.inputs['To Min'].default_value=1.;young.inputs['To Max'].default_value=.08
 links.new(age.outputs['Fac'],young.inputs['Value'])
 vis=math_node(nodes,'MULTIPLY');links.new(thin.outputs['Result'],vis.inputs[0]);links.new(young.outputs['Result'],vis.inputs[1])
 est=math_node(nodes,'MULTIPLY');links.new(thermal.outputs['Fac'],est.inputs[0]);links.new(vis.outputs[0],est.inputs[1])
 escale=math_node(nodes,'MULTIPLY',b=.42,label='faint heat through young crust');links.new(est.outputs[0],escale.inputs[0])
 links.new(escale.outputs[0],p.inputs['Emission Strength'])

 tr=nodes.new('ShaderNodeMapRange');tr.clamp=True
 tr.inputs['From Min'].default_value=950.;tr.inputs['From Max'].default_value=1550.
 tr.inputs['To Min'].default_value=0.;tr.inputs['To Max'].default_value=1.
 links.new(temp.outputs['Fac'],tr.inputs['Value'])
 ramp=nodes.new('ShaderNodeValToRGB');ramp.color_ramp.interpolation='EASE'
 e0=ramp.color_ramp.elements[0];e0.position=0.;e0.color=(.06,0.,0.,1.)
 e1=ramp.color_ramp.elements[1];e1.position=1.;e1.color=(1.,.31,.01,1.)
 e2=ramp.color_ramp.elements.new(.58);e2.color=(.50,.025,0.,1.)
 links.new(tr.outputs['Result'],ramp.inputs['Fac']);links.new(ramp.outputs['Color'],p.inputs['Emission Color'])

 bump=nodes.new('ShaderNodeBump');bump.label='sub-grid crust grain';bump.inputs['Strength'].default_value=.18;bump.inputs['Distance'].default_value=.00055
 links.new(micro.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],p.inputs['Normal'])
 return lava


def build_molten_material():
 m,p=principled('Molten basalt interior / breakout surface')
 p.inputs['Metallic'].default_value=0.;p.inputs['Roughness'].default_value=.48;p.inputs['IOR'].default_value=1.54
 if 'Specular IOR Level' in p.inputs:p.inputs['Specular IOR Level'].default_value=.12
 if 'Coat Weight' in p.inputs:p.inputs['Coat Weight'].default_value=0.
 nodes=m.node_tree.nodes;links=m.node_tree.links
 bulk_temperature=attribute(nodes,'bulkTemperature')
 bulk_strength=attribute(nodes,'bulkThermalStrength')
 rest=attribute(nodes,'materialCoordinates')

 tr=nodes.new('ShaderNodeMapRange');tr.clamp=True
 tr.inputs['From Min'].default_value=1000.;tr.inputs['From Max'].default_value=1650.
 tr.inputs['To Min'].default_value=0.;tr.inputs['To Max'].default_value=1.
 links.new(bulk_temperature.outputs['Fac'],tr.inputs['Value'])
 ramp=nodes.new('ShaderNodeValToRGB');ramp.color_ramp.interpolation='EASE'
 e0=ramp.color_ramp.elements[0];e0.position=0.;e0.color=(.015,0.,0.,1.)
 e1=ramp.color_ramp.elements[1];e1.position=1.;e1.color=(1.,.34,.012,1.)
 e2=ramp.color_ramp.elements.new(.34);e2.color=(.17,.002,0.,1.)
 e3=ramp.color_ramp.elements.new(.66);e3.color=(.72,.045,.001,1.)
 e4=ramp.color_ramp.elements.new(.84);e4.color=(1.,.19,.004,1.)
 links.new(tr.outputs['Result'],ramp.inputs['Fac']);links.new(ramp.outputs['Color'],p.inputs['Emission Color'])

 macro=nodes.new('ShaderNodeTexNoise');macro.noise_dimensions='3D';macro.label='sub-grid emissivity variation'
 macro.inputs['Scale'].default_value=12.;macro.inputs['Detail'].default_value=2.7;macro.inputs['Roughness'].default_value=.63
 links.new(rest.outputs['Vector'],macro.inputs['Vector'])
 mod=nodes.new('ShaderNodeMapRange');mod.clamp=True
 mod.inputs['From Min'].default_value=.16;mod.inputs['From Max'].default_value=.84
 mod.inputs['To Min'].default_value=.28;mod.inputs['To Max'].default_value=1.02
 links.new(macro.outputs['Fac'],mod.inputs['Value'])
 sm=math_node(nodes,'MULTIPLY');links.new(bulk_strength.outputs['Fac'],sm.inputs[0]);links.new(mod.outputs['Result'],sm.inputs[1])
 scale=math_node(nodes,'MULTIPLY',b=.82,label='exposed interior radiance');links.new(sm.outputs[0],scale.inputs[0]);links.new(scale.outputs[0],p.inputs['Emission Strength'])

 base_mix=nodes.new('ShaderNodeMixRGB');base_mix.blend_type='MIX';base_mix.inputs['Fac'].default_value=.22
 base_mix.inputs[1].default_value=(.006,.001,.00018,1.);links.new(ramp.outputs['Color'],base_mix.inputs[2]);links.new(base_mix.outputs['Color'],p.inputs['Base Color'])
 bump=nodes.new('ShaderNodeBump');bump.label='viscous breakout relief';bump.inputs['Strength'].default_value=.15;bump.inputs['Distance'].default_value=.00080
 links.new(macro.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],p.inputs['Normal'])
 return m


def add_float_attribute(mesh,name,values):
 values=np.asarray(values,np.float32)
 attr=mesh.attributes.new(name,'FLOAT','POINT');attr.data.foreach_set('value',values.ravel())
 return attr


def add_vector_attribute(mesh,name,values):
 values=np.asarray(values,np.float32)
 attr=mesh.attributes.new(name,'FLOAT_VECTOR','POINT');attr.data.foreach_set('vector',values.ravel())
 return attr


def add_color_attribute(mesh,name,values):
 rgb=np.asarray(values,np.float32)
 rgba=np.column_stack([rgb,np.ones(len(rgb),np.float32)])
 attr=mesh.color_attributes.new(name=name,type='FLOAT_COLOR',domain='POINT');attr.data.foreach_set('color',rgba.ravel())
 return attr


def bilinear(field,y,x):
 h,w=field.shape
 x=np.clip(x,0,w-1.000001);y=np.clip(y,0,h-1.000001)
 x0=np.floor(x).astype(np.int64);y0=np.floor(y).astype(np.int64)
 x1=np.minimum(x0+1,w-1);y1=np.minimum(y0+1,h-1)
 fx=x-x0;fy=y-y0
 return ((1-fx)*(1-fy)*field[y0,x0]+fx*(1-fy)*field[y0,x1]+
         (1-fx)*fy*field[y1,x0]+fx*fy*field[y1,x1])


def build_mold(source,formation,floor_height,mold_path=None):
 if not formation:return None
 if mold_path is not None and Path(mold_path).is_file():
  with np.load(mold_path,allow_pickle=False) as data:
   verts=np.asarray(data['vertices'],np.float64);faces=np.asarray(data['faces'],np.int32)
 else:
  with np.load(source,allow_pickle=False) as data:
   sdf=np.asarray(data['sdf'],np.float64);lo=np.asarray(data['lo'],np.float64);extent=np.asarray(data['extent'],np.float64)
  scale=float(formation['stage_scale']);center=float(formation['source_center_z']);wall=float(formation['wall_height'])
  nx,ny=184,84
  xs=np.linspace(-.74,.74,nx);ys=np.linspace(-.36,.36,ny);xx,yy=np.meshgrid(xs,ys,indexing='xy')
  sx=xx/scale;sz=yy/scale+center
  u=(sx-lo[0])/extent[0]*(sdf.shape[1]-1);v=(sz-lo[2])/extent[2]*(sdf.shape[0]-1)
  d=bilinear(sdf,v,u)*scale
  t=np.clip((.006-d)/.012,0,1);t=t*t*(3-2*t)
  zz=floor_height+wall*t
  verts=np.column_stack([xx.ravel(),yy.ravel(),zz.ravel()])
  faces=[]
  for j in range(ny-1):
   for i in range(nx-1):
    a=j*nx+i;b=a+1;c=a+nx;d0=c+1
    faces.extend([(a,b,d0),(a,d0,c)])
  faces=np.asarray(faces,np.int32)
 me=bpy.data.meshes.new('Basalt glyph mold');me.from_pydata(verts.tolist(),[],faces.tolist());me.update()
 obj=bpy.data.objects.new('Basalt glyph mold',me);bpy.context.collection.objects.link(obj)
 material,p=principled('Basalt mold / closed cavity geometry')
 p.inputs['Base Color'].default_value=(.050,.056,.066,1);p.inputs['Roughness'].default_value=.80;p.inputs['IOR'].default_value=1.52
 if 'Coat Weight' in p.inputs:p.inputs['Coat Weight'].default_value=.025
 nodes=material.node_tree.nodes;links=material.node_tree.links
 tc=nodes.new('ShaderNodeTexCoord');noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=82;noise.inputs['Detail'].default_value=3.6;noise.inputs['Roughness'].default_value=.68
 links.new(tc.outputs['Generated'],noise.inputs['Vector'])
 bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.10;bump.inputs['Distance'].default_value=.0008
 links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],p.inputs['Normal'])
 me.materials.append(material)
 for poly in me.polygons:poly.use_smooth=False
 bevel=obj.modifiers.new('Subtle manufactured stone edge','BEVEL');bevel.width=.0024;bevel.segments=2
 return obj


def main():
 a=parser();wait_for(a.surface/'run.json',timeout=a.wait_timeout);surface_settings=json.loads((a.surface/'run.json').read_text())['settings'];floor_height=float(surface_settings['floor']);formation=surface_settings.get('formation');formation_mode=surface_settings.get('formationMode','formed');bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.device='CPU';s.render.threads_mode='FIXED';s.render.threads=a.threads
 s.cycles.samples=a.samples;s.cycles.use_adaptive_sampling=True;s.cycles.adaptive_threshold=.018
 s.cycles.use_denoising=True;s.cycles.denoiser='OPENIMAGEDENOISE'
 s.cycles.max_bounces=12;s.cycles.diffuse_bounces=5;s.cycles.glossy_bounces=7
 s.cycles.transmission_bounces=8;s.cycles.volume_bounces=2
 s.cycles.sample_clamp_direct=0;s.cycles.sample_clamp_indirect=0
 s.render.resolution_x,s.render.resolution_y=a.resolution;s.render.resolution_percentage=100
 s.render.fps=a.fps;s.render.film_transparent=False
 s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast';s.view_settings.exposure=a.exposure
 s.world=bpy.data.worlds.new('Dim neutral studio');s.world.use_nodes=True
 bg=s.world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(.052,.058,.070,1);bg.inputs['Strength'].default_value=.036 if formation_mode=='pour' else .040
 bpy.ops.object.camera_add();camera=bpy.context.object;s.camera=camera
 view=('formation' if formation_mode=='pour' else 'oblique') if a.view=='auto' else a.view
 target=(0.,0.,.10 if view=='formation' else .335)
 positions={'formation':(.48,-1.30,1.95),'oblique':(.82,-2.65,1.03),'front':(0.,-3.,.5),'overhead':(.62,-1.75,1.8)}
 camera.location=positions[view];camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
 camera.data.type='ORTHO';camera.data.ortho_scale=1.52 if view=='formation' else 1.65;camera.data.clip_start=.01;camera.data.clip_end=30
 if view=='formation':
  area('Large neutral key',(-.62,-.70,1.55),11.0,(.90,.93,1.),1.85,target)
  area('Long grazing rim',(.72,.62,.72),15.0,(.76,.84,1.),1.18,target)
  area('Soft warm fill',(-.20,-.92,.55),3.4,(1.,.84,.68),1.90,target)
  area('Obsidian edge kicker',(.18,.48,.42),4.5,(.72,.82,1.),.78,target)
 else:
  area('Large neutral key',(-.55,-.75,1.45),42,(.90,.93,1.),1.15,target)
  area('Grazing rim',(.65,.6,1.1),62,(.83,.88,.97),.88,target)
  area('Soft front fill',(-.3,-1.,.55),9,(1.,.90,.78),1.35,target)
 floor,fp=principled('Fine basalt stage');fp.inputs['Base Color'].default_value=(.018,.021,.027,1);fp.inputs['Roughness'].default_value=.86
 n=floor.node_tree.nodes;l=floor.node_tree.links
 tc=n.new('ShaderNodeTexCoord');noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=95;noise.inputs['Detail'].default_value=4
 l.new(tc.outputs['Object'],noise.inputs['Vector']);bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.21;bump.inputs['Distance'].default_value=.0014
 l.new(noise.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],fp.inputs['Normal'])
 bpy.ops.mesh.primitive_plane_add(size=8,location=(0,0,floor_height-.0015));bpy.context.object.data.materials.append(floor)
 mold=build_mold(a.source,formation,floor_height,a.surface/'mold.npz') if formation_mode=='pour' else None
 crust_material=build_lava_material()
 molten_material=build_molten_material()
 settings={'device':'CPU','engine':'Cycles','blender':bpy.app.version_string,'resolution':a.resolution,'samples':a.samples,
  'adaptiveThreshold':.018,'denoiser':'OpenImageDenoise','fps':a.fps,'frames':a.frames,'frame':a.frame,
  'floor':floor_height,'exposure':a.exposure,'view':view,'formationMode':formation_mode,'formation':formation,'viewTransform':'AgX','look':'Medium High Contrast','motionBlur':False,
  'material':'separate incandescent interior geometry beneath finite moving crust rafts with resolved age/thickness/strain/tear state',
  'subgridDisclosure':'shell holes and raft offsets are geometry; scalar tear openness is solver state; procedural textures only add sub-grid roughness and vesicles'}
 render_inputs={'surfaceRun':a.surface/'run.json','entry':Path(__file__),'materialControls':Path(__file__).parent/'elements_core/lava_material.py'}
 if formation_mode=='pour':
  render_inputs['moldSource']=a.source
  if (a.surface/'mold.npz').is_file():render_inputs['moldMesh']=a.surface/'mold.npz'
 run=RunIdentity(a.out,settings,render_inputs)
 (a.out/'frames').mkdir(exist_ok=True);atomic_json(a.out/'render-settings.json',settings)
 o_interior=None;o_crust=None;start=time.perf_counter();rows=[]
 for f in ([a.frame] if a.frame is not None else range(a.frames)):
  src=a.surface/'meshes'/f'{f:04d}.npz';deadline=time.monotonic()+a.wait_timeout
  while not src.exists():
   if time.monotonic()>deadline:raise TimeoutError(src)
   time.sleep(1)
  with np.load(src,allow_pickle=False) as data:
   if abs(float(data['time'])-f/a.fps)>1e-7:raise RuntimeError('Mesh and camera clock disagree')

   # Continuous incandescent interior.
   ime=bpy.data.meshes.new(f'molten interior {f:04d}')
   ime.from_pydata(data['vertices'].tolist(),[],data['faces'].tolist());ime.update()
   if o_interior is None:
    o_interior=bpy.data.objects.new('Molten lava interior',ime);bpy.context.collection.objects.link(o_interior)
   else:
    old=o_interior.data;o_interior.data=ime;bpy.data.meshes.remove(old)
   ime.materials.append(molten_material)
   for poly in ime.polygons:poly.use_smooth=True
   bulk_temp=np.asarray(data['bulkTemperature'],np.float64) if 'bulkTemperature' in data else np.asarray(data['temperature'],np.float64)
   interior_tear=np.asarray(data['tearOpen'],np.float64) if 'tearOpen' in data else np.zeros(len(bulk_temp))
   bulk_controls=material_controls(bulk_temp,np.zeros_like(bulk_temp))
   add_float_attribute(ime,'bulkTemperature',bulk_temp)
   add_float_attribute(ime,'bulkThermalStrength',bulk_controls['thermalStrength'])
   add_float_attribute(ime,'tearOpen',interior_tear)
   add_vector_attribute(ime,'materialCoordinates',data['rest'])

   # Finite crust raft shell. Empty at the earliest fully molten frames.
   if 'crustVertices' in data:
    cverts=np.asarray(data['crustVertices'],np.float64);cfaces=np.asarray(data['crustFaces'],np.int32)
   else:
    cverts=np.asarray(data['vertices'],np.float64);cfaces=np.asarray(data['faces'],np.int32)
   cme=bpy.data.meshes.new(f'crust shell {f:04d}')
   cme.from_pydata(cverts.tolist(),[],cfaces.tolist());cme.update()
   if o_crust is None:
    o_crust=bpy.data.objects.new('Finite lava crust rafts',cme);bpy.context.collection.objects.link(o_crust)
   else:
    old=o_crust.data;o_crust.data=cme;bpy.data.meshes.remove(old)
   cme.materials.append(crust_material)
   for poly in cme.polygons:poly.use_smooth=True

   if len(cverts):
    temp=np.asarray(data['crustTemperature'],np.float64) if 'crustTemperature' in data else np.asarray(data['temperature'],np.float64)
    damage=np.asarray(data['crustDamage'],np.float64) if 'crustDamage' in data else np.asarray(data['damage'],np.float64)
    crust_bulk=np.asarray(data['crustBulkTemperature'],np.float64) if 'crustBulkTemperature' in data else bulk_temp.copy()
    surface_age=np.asarray(data['crustSurfaceAge'],np.float64) if 'crustSurfaceAge' in data else np.zeros_like(temp)
    strain_history=np.asarray(data['crustStrainHistory'],np.float64) if 'crustStrainHistory' in data else np.zeros_like(temp)
    tear_open=np.asarray(data['crustTearOpen'],np.float64) if 'crustTearOpen' in data else np.zeros_like(temp)
    crust_thickness=np.asarray(data['crustThickness'],np.float64) if 'crustThickness' in data else np.zeros_like(temp)
    controls=material_controls(temp,damage)
    crust_bulk_controls=material_controls(crust_bulk,np.zeros_like(damage))
    add_float_attribute(cme,'temperature',temp)
    add_float_attribute(cme,'bulkTemperature',crust_bulk)
    add_float_attribute(cme,'bulkThermalStrength',crust_bulk_controls['thermalStrength'])
    add_float_attribute(cme,'damage',damage)
    add_float_attribute(cme,'surfaceAge',surface_age)
    add_float_attribute(cme,'strainHistory',strain_history)
    add_float_attribute(cme,'tearOpen',tear_open)
    add_float_attribute(cme,'crustThickness',crust_thickness)
    add_float_attribute(cme,'crustAmount',controls['crust'])
    add_float_attribute(cme,'fracturePotential',controls['fracture'])
    add_float_attribute(cme,'reliefAmount',controls['relief'])
    add_float_attribute(cme,'obsidianAmount',controls['obsidian'])
    add_float_attribute(cme,'meltAmount',controls['melt'])
    add_float_attribute(cme,'roughnessBase',controls['roughness'])
    add_float_attribute(cme,'coatWeight',controls['coat'])
    add_vector_attribute(cme,'materialCoordinates',data['crustRest'] if 'crustRest' in data else data['rest'])
    add_color_attribute(cme,'baseColor',controls['baseColor'])
    add_color_attribute(cme,'thermalRadiance',controls['thermalRadiance'])
    add_color_attribute(cme,'thermalColor',controls['thermalColor'])
    add_float_attribute(cme,'thermalStrength',controls['thermalStrength'])
   else:
    temp=np.array([surface_settings.get('config',{}).get('feed_skin_temperature',1435.)])
    surface_age=strain_history=tear_open=crust_thickness=np.zeros(1)
    controls=material_controls(temp,np.zeros(1))

  s.frame_set(f);s.cycles.seed=1739+f
  exr=a.out/'frames'/f'{f:04d}.exr';png=a.out/'frames'/f'{f:04d}.png'
  s.render.image_settings.file_format='OPEN_EXR';s.render.image_settings.color_mode='RGBA';s.render.image_settings.color_depth='32';s.render.filepath=str(exr)
  bpy.ops.render.render(write_still=True)
  s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.color_depth='8'
  bpy.data.images['Render Result'].save_render(str(png),scene=s)
  run.receipt(f'render-{f:04d}',[exr,png],frame=f,sourceSHA256=digest(src))
  row={'frame':f,'time':f/a.fps,'sourceSHA256':digest(src),
       'interiorVertices':len(ime.vertices),'interiorTriangles':len(ime.polygons),
       'crustVertices':len(cme.vertices),'crustTriangles':len(cme.polygons),
       'bulkTemperatureMinK':float(bulk_temp.min()),'bulkTemperatureMaxK':float(bulk_temp.max()),
       'crustMean':float(controls['crust'].mean()),
       'surfaceAgeMeanSeconds':float(surface_age.mean()),
       'strainHistoryMean':float(strain_history.mean()),
       'tearOpenMean':float(tear_open.mean()),'tearOpenMax':float(tear_open.max()),
       'crustThicknessMeanM':float(crust_thickness.mean()),
       'obsidianMean':float(controls['obsidian'].mean()),
       'thermalStrengthMean':float(controls['thermalStrength'].mean()),
       'wallSeconds':time.perf_counter()-start}
  rows.append(row);atomic_json(a.out/'frames'/f'{f:04d}.json',row);print('LAVA_FRAME',json.dumps(row),flush=True)
  if a.save_blend:bpy.ops.wm.save_as_mainfile(filepath=str(a.out/f'frame-{f:04d}.blend'))
 atomic_json(a.out/'manifest.json',dict(complete=True,frames=len(rows),fps=a.fps,resolution=a.resolution,
   noFrameInterpolation=True,noImageGeneration=True,elapsedSeconds=time.perf_counter()-start,settings=settings))
if __name__=='__main__':main()
