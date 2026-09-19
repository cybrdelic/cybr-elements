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
 lava,p=principled('Thermal continuum / resolved state + material-coordinate crust')
 p.inputs['Metallic'].default_value=0.
 p.inputs['IOR'].default_value=1.52
 if 'Specular IOR Level' in p.inputs:p.inputs['Specular IOR Level'].default_value=.12
 p.inputs['Coat Roughness'].default_value=.18
 nodes=lava.node_tree.nodes;links=lava.node_tree.links
 base=attribute(nodes,'baseColor')
 rough_base=attribute(nodes,'roughnessBase')
 coat=attribute(nodes,'coatWeight')
 thermal=attribute(nodes,'thermalColor')
 thermal_strength=attribute(nodes,'thermalStrength')
 temperature=attribute(nodes,'temperature')
 rest=attribute(nodes,'materialCoordinates')
 fracture=attribute(nodes,'fracturePotential')
 crust=attribute(nodes,'crustAmount')
 relief=attribute(nodes,'reliefAmount')
 obsidian=attribute(nodes,'obsidianAmount')
 melt=attribute(nodes,'meltAmount')
 links.new(base.outputs['Color'],p.inputs['Base Color'])
 blackbody=nodes.new('ShaderNodeBlackbody');blackbody.label='temperature-derived blackbody chroma'
 links.new(temperature.outputs['Fac'],blackbody.inputs['Temperature'])
 links.new(blackbody.outputs['Color'],p.inputs['Emission Color'])

 macro=nodes.new('ShaderNodeTexNoise');macro.noise_dimensions='3D';macro.label='advected crust macrostructure'
 macro.inputs['Scale'].default_value=23.;macro.inputs['Detail'].default_value=5.2
 macro.inputs['Roughness'].default_value=.72;macro.inputs['Distortion'].default_value=.17
 links.new(rest.outputs['Vector'],macro.inputs['Vector'])
 micro=nodes.new('ShaderNodeTexNoise');micro.noise_dimensions='3D';micro.label='advected vesicle microstructure'
 micro.inputs['Scale'].default_value=185.;micro.inputs['Detail'].default_value=4.5
 micro.inputs['Roughness'].default_value=.78;micro.inputs['Distortion'].default_value=.08
 links.new(rest.outputs['Vector'],micro.inputs['Vector'])

 cells=nodes.new('ShaderNodeTexVoronoi');cells.voronoi_dimensions='3D';cells.feature='DISTANCE_TO_EDGE';cells.distance='EUCLIDEAN'
 cells.label='damage-gated sub-grid crust edges';cells.inputs['Scale'].default_value=18.
 links.new(rest.outputs['Vector'],cells.inputs['Vector'])
 edge=nodes.new('ShaderNodeMapRange');edge.clamp=True;edge.interpolation_type='SMOOTHERSTEP';edge.label='thin cellular edges'
 edge.inputs['From Min'].default_value=.010;edge.inputs['From Max'].default_value=.052
 edge.inputs['To Min'].default_value=1.;edge.inputs['To Max'].default_value=0.
 links.new(cells.outputs['Distance'],edge.inputs['Value'])
 fracture_edge=math_node(nodes,'MULTIPLY',label='resolved damage × sub-grid edge')
 links.new(fracture.outputs['Fac'],fracture_edge.inputs[0]);links.new(edge.outputs['Result'],fracture_edge.inputs[1])

 # Cooling crust is optically opaque: thermal radiance is visible through
 # resolved melt and re-opens locally along damage-gated fissures.
 fissure_glow=math_node(nodes,'MULTIPLY',b=.82,label='fissure thermal reveal')
 links.new(fracture_edge.outputs[0],fissure_glow.inputs[0])
 glow_floor=math_node(nodes,'ADD',a=.004,label='minimum subsurface leak')
 links.new(fissure_glow.outputs[0],glow_floor.inputs[1])
 emission_visibility=math_node(nodes,'MAXIMUM',label='melt or fissure visibility')
 links.new(melt.outputs['Fac'],emission_visibility.inputs[0]);links.new(glow_floor.outputs[0],emission_visibility.inputs[1])
 # Sub-grid cooling-skin heterogeneity: the resolved crust fraction says how
 # much skin is present; transported noise only distributes that resolved amount
 # into irregular islands. It never creates a hidden hot region or motion field.
 skin_noise=nodes.new('ShaderNodeTexNoise');skin_noise.noise_dimensions='3D';skin_noise.label='resolved-crust island distribution'
 skin_noise.inputs['Scale'].default_value=8.5;skin_noise.inputs['Detail'].default_value=2.6
 skin_noise.inputs['Roughness'].default_value=.63;skin_noise.inputs['Distortion'].default_value=.11
 links.new(rest.outputs['Vector'],skin_noise.inputs['Vector'])
 skin_shape=nodes.new('ShaderNodeMapRange');skin_shape.clamp=True;skin_shape.interpolation_type='SMOOTHERSTEP'
 skin_shape.inputs['From Min'].default_value=.42;skin_shape.inputs['From Max'].default_value=.58
 skin_shape.inputs['To Min'].default_value=0.;skin_shape.inputs['To Max'].default_value=1.
 links.new(skin_noise.outputs['Fac'],skin_shape.inputs['Value'])
 crust_gain=math_node(nodes,'MULTIPLY',b=3.7,label='resolved crust coverage gain')
 links.new(crust.outputs['Fac'],crust_gain.inputs[0])
 skin_raw=math_node(nodes,'MULTIPLY',label='resolved crust × island distribution')
 links.new(crust_gain.outputs[0],skin_raw.inputs[0]);links.new(skin_shape.outputs['Result'],skin_raw.inputs[1])
 skin_clamp=nodes.new('ShaderNodeClamp');skin_clamp.inputs['Min'].default_value=0.;skin_clamp.inputs['Max'].default_value=1.
 links.new(skin_raw.outputs[0],skin_clamp.inputs['Value'])
 skin_cut=math_node(nodes,'MULTIPLY',b=-.94,label='opaque cooling skin')
 links.new(skin_clamp.outputs['Result'],skin_cut.inputs[0])
 skin_keep=math_node(nodes,'ADD',a=1.,label='thermal visibility through broken skin')
 links.new(skin_cut.outputs[0],skin_keep.inputs[1])

 emission_strength=math_node(nodes,'MULTIPLY',label='blackbody × visible molten fraction')
 links.new(thermal_strength.outputs['Fac'],emission_strength.inputs[0]);links.new(emission_visibility.outputs[0],emission_strength.inputs[1])
 skin_emission=math_node(nodes,'MULTIPLY',label='blackbody through resolved skin islands')
 links.new(emission_strength.outputs[0],skin_emission.inputs[0]);links.new(skin_keep.outputs[0],skin_emission.inputs[1])
 emission_scale=math_node(nodes,'MULTIPLY',b=1.45,label='camera-scale thermal radiance')
 links.new(skin_emission.outputs[0],emission_scale.inputs[0]);links.new(emission_scale.outputs[0],p.inputs['Emission Strength'])

 macro_gain=nodes.new('ShaderNodeMapRange');macro_gain.clamp=True
 macro_gain.inputs['From Min'].default_value=.12;macro_gain.inputs['From Max'].default_value=.88
 macro_gain.inputs['To Min'].default_value=.72;macro_gain.inputs['To Max'].default_value=1.24
 links.new(macro.outputs['Fac'],macro_gain.inputs['Value'])
 macro_gate=nodes.new('ShaderNodeMixRGB');macro_gate.blend_type='MIX';macro_gate.label='crust-only albedo breakup'
 macro_gate.inputs[1].default_value=(1.,1.,1.,1.)
 links.new(crust.outputs['Fac'],macro_gate.inputs['Fac']);links.new(macro_gain.outputs['Result'],macro_gate.inputs[2])
 base_mod=nodes.new('ShaderNodeMixRGB');base_mod.blend_type='MULTIPLY';base_mod.inputs['Fac'].default_value=1.
 links.new(base.outputs['Color'],base_mod.inputs[1]);links.new(macro_gate.outputs['Color'],base_mod.inputs[2])
 skin_albedo=nodes.new('ShaderNodeMixRGB');skin_albedo.blend_type='MULTIPLY';skin_albedo.label='dark crust plate albedo'
 links.new(skin_clamp.outputs['Result'],skin_albedo.inputs['Fac']);links.new(base_mod.outputs['Color'],skin_albedo.inputs[1])
 skin_albedo.inputs[2].default_value=(.12,.13,.14,1.)
 fracture_dark=nodes.new('ShaderNodeMixRGB');fracture_dark.blend_type='MULTIPLY'
 links.new(fracture_edge.outputs[0],fracture_dark.inputs['Fac']);links.new(skin_albedo.outputs['Color'],fracture_dark.inputs[1])
 fracture_dark.inputs[2].default_value=(.020,.012,.006,1.)
 links.new(fracture_dark.outputs['Color'],p.inputs['Base Color'])

 micro_center=math_node(nodes,'SUBTRACT',b=.5,label='micro centered');links.new(micro.outputs['Fac'],micro_center.inputs[0])
 micro_amp=math_node(nodes,'MULTIPLY',b=.09,label='micro roughness amplitude');links.new(micro_center.outputs[0],micro_amp.inputs[0])
 micro_phase=math_node(nodes,'MULTIPLY',label='crust-gated micro roughness');links.new(micro_amp.outputs[0],micro_phase.inputs[0]);links.new(relief.outputs['Fac'],micro_phase.inputs[1])
 rough_add=math_node(nodes,'ADD',label='phase roughness + cooled microstructure');links.new(rough_base.outputs['Fac'],rough_add.inputs[0]);links.new(micro_phase.outputs[0],rough_add.inputs[1])
 fracture_rough=math_node(nodes,'MULTIPLY',b=.055,label='fracture roughness');links.new(fracture_edge.outputs[0],fracture_rough.inputs[0])
 rough_total=math_node(nodes,'ADD');links.new(rough_add.outputs[0],rough_total.inputs[0]);links.new(fracture_rough.outputs[0],rough_total.inputs[1])
 rough_clamp=nodes.new('ShaderNodeClamp');rough_clamp.inputs['Min'].default_value=.16;rough_clamp.inputs['Max'].default_value=.98
 links.new(rough_total.outputs[0],rough_clamp.inputs['Value']);links.new(rough_clamp.outputs['Result'],p.inputs['Roughness'])

 ripple=nodes.new('ShaderNodeTexNoise');ripple.noise_dimensions='3D';ripple.label='viscous molten surface ripple'
 ripple.inputs['Scale'].default_value=46.;ripple.inputs['Detail'].default_value=2.0
 ripple.inputs['Roughness'].default_value=.52;ripple.inputs['Distortion'].default_value=.10
 links.new(rest.outputs['Vector'],ripple.inputs['Vector'])
 ripple_bump=nodes.new('ShaderNodeBump');ripple_bump.label='melt-only ripple normal';ripple_bump.inputs['Distance'].default_value=.00080
 ripple_strength=math_node(nodes,'MULTIPLY',a=.10,label='melt ripple strength');links.new(melt.outputs['Fac'],ripple_strength.inputs[1]);links.new(ripple_strength.outputs[0],ripple_bump.inputs['Strength'])
 links.new(ripple.outputs['Fac'],ripple_bump.inputs['Height'])

 macro_bump=nodes.new('ShaderNodeBump');macro_bump.label='cooled skin relief';macro_bump.inputs['Strength'].default_value=.24;macro_bump.inputs['Distance'].default_value=.0022
 links.new(macro.outputs['Fac'],macro_bump.inputs['Height']);links.new(ripple_bump.outputs['Normal'],macro_bump.inputs['Normal'])
 macro_strength=math_node(nodes,'MULTIPLY',a=.38,label='phase relief weight');links.new(relief.outputs['Fac'],macro_strength.inputs[1]);links.new(macro_strength.outputs[0],macro_bump.inputs['Strength'])
 micro_bump=nodes.new('ShaderNodeBump');micro_bump.label='grain-scale relief';micro_bump.inputs['Distance'].default_value=.00048
 micro_bump_strength=math_node(nodes,'MULTIPLY',a=.16,label='crust-gated grain relief');links.new(relief.outputs['Fac'],micro_bump_strength.inputs[1]);links.new(micro_bump_strength.outputs[0],micro_bump.inputs['Strength'])
 links.new(micro.outputs['Fac'],micro_bump.inputs['Height']);links.new(macro_bump.outputs['Normal'],micro_bump.inputs['Normal'])
 vesicles=nodes.new('ShaderNodeTexVoronoi');vesicles.voronoi_dimensions='3D';vesicles.feature='F1';vesicles.distance='EUCLIDEAN'
 vesicles.label='advected vesicle centers';vesicles.inputs['Scale'].default_value=118.
 links.new(rest.outputs['Vector'],vesicles.inputs['Vector'])
 pit=nodes.new('ShaderNodeMapRange');pit.clamp=True;pit.interpolation_type='SMOOTHERSTEP';pit.label='vesicle pits'
 pit.inputs['From Min'].default_value=.035;pit.inputs['From Max'].default_value=.145
 pit.inputs['To Min'].default_value=1.;pit.inputs['To Max'].default_value=0.
 links.new(vesicles.outputs['Distance'],pit.inputs['Value'])
 pit_gate=math_node(nodes,'MULTIPLY',label='phase-gated vesicles');links.new(relief.outputs['Fac'],pit_gate.inputs[0]);links.new(pit.outputs['Result'],pit_gate.inputs[1])
 pit_bump=nodes.new('ShaderNodeBump');pit_bump.label='quenched vesicle depressions';pit_bump.invert=True;pit_bump.inputs['Strength'].default_value=.38;pit_bump.inputs['Distance'].default_value=.00105
 links.new(pit_gate.outputs[0],pit_bump.inputs['Height']);links.new(micro_bump.outputs['Normal'],pit_bump.inputs['Normal'])
 fissure_bump=nodes.new('ShaderNodeBump');fissure_bump.label='damage-gated crease';fissure_bump.invert=True;fissure_bump.inputs['Strength'].default_value=.46;fissure_bump.inputs['Distance'].default_value=.00085
 links.new(fracture_edge.outputs[0],fissure_bump.inputs['Height']);links.new(pit_bump.outputs['Normal'],fissure_bump.inputs['Normal']);links.new(fissure_bump.outputs['Normal'],p.inputs['Normal'])
 crack_coat=math_node(nodes,'MULTIPLY',a=-.82,label='coat loss in fissures');links.new(fracture_edge.outputs[0],crack_coat.inputs[1])
 coat_keep=math_node(nodes,'ADD',a=1.,label='fissure coat mask');links.new(crack_coat.outputs[0],coat_keep.inputs[1])
 coat_final=math_node(nodes,'MULTIPLY',label='phase coat × fissure mask');links.new(coat.outputs['Fac'],coat_final.inputs[0]);links.new(coat_keep.outputs[0],coat_final.inputs[1])
 links.new(coat_final.outputs[0],p.inputs['Coat Weight'])

 coat_rough=math_node(nodes,'MULTIPLY',b=.75,label='coat roughness from phase');links.new(rough_clamp.outputs['Result'],coat_rough.inputs[0]);links.new(coat_rough.outputs[0],p.inputs['Coat Roughness'])
 return lava


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
 lava=build_lava_material()
 settings={'device':'CPU','engine':'Cycles','blender':bpy.app.version_string,'resolution':a.resolution,'samples':a.samples,
  'adaptiveThreshold':.018,'denoiser':'OpenImageDenoise','fps':a.fps,'frames':a.frames,'frame':a.frame,
  'floor':floor_height,'exposure':a.exposure,'view':view,'formationMode':formation_mode,'formation':formation,'viewTransform':'AgX','look':'Medium High Contrast','motionBlur':False,
  'material':'resolved temperature/damage phase controls + normalized Planck-band chroma + explicit visible-radiance-to-scene strength + transported-coordinate multiscale crust relief',
  'subgridDisclosure':'noise/voronoi are BSDF microstructure anchored to material coordinates; damage gates crease relief; no resolved crack geometry is claimed'}
 render_inputs={'surfaceRun':a.surface/'run.json','entry':Path(__file__),'materialControls':Path(__file__).parent/'elements_core/lava_material.py'}
 if formation_mode=='pour':
  render_inputs['moldSource']=a.source
  if (a.surface/'mold.npz').is_file():render_inputs['moldMesh']=a.surface/'mold.npz'
 run=RunIdentity(a.out,settings,render_inputs)
 (a.out/'frames').mkdir(exist_ok=True);atomic_json(a.out/'render-settings.json',settings)
 o=None;start=time.perf_counter();rows=[]
 for f in ([a.frame] if a.frame is not None else range(a.frames)):
  src=a.surface/'meshes'/f'{f:04d}.npz';deadline=time.monotonic()+a.wait_timeout
  while not src.exists():
   if time.monotonic()>deadline:raise TimeoutError(src)
   time.sleep(1)
  with np.load(src,allow_pickle=False) as data:
   if abs(float(data['time'])-f/a.fps)>1e-7:raise RuntimeError('Mesh and camera clock disagree')
   me=bpy.data.meshes.new(f'thermal continuum {f:04d}')
   me.from_pydata(data['vertices'].tolist(),[],data['faces'].tolist());me.update()
   if o is None:o=bpy.data.objects.new('Deforming lava',me);bpy.context.collection.objects.link(o)
   else:
    old=o.data;o.data=me;bpy.data.meshes.remove(old)
   me.materials.append(lava)
   for poly in me.polygons:poly.use_smooth=True
   temp=np.asarray(data['temperature'],np.float64);damage=np.asarray(data['damage'],np.float64)
   controls=material_controls(temp,damage)
   add_float_attribute(me,'temperature',temp)
   add_float_attribute(me,'damage',damage)
   add_float_attribute(me,'crustAmount',controls['crust'])
   add_float_attribute(me,'fracturePotential',controls['fracture'])
   add_float_attribute(me,'reliefAmount',controls['relief'])
   add_float_attribute(me,'obsidianAmount',controls['obsidian'])
   add_float_attribute(me,'meltAmount',controls['melt'])
   add_float_attribute(me,'roughnessBase',controls['roughness'])
   add_float_attribute(me,'coatWeight',controls['coat'])
   add_vector_attribute(me,'materialCoordinates',data['rest'])
   add_color_attribute(me,'baseColor',controls['baseColor'])
   add_color_attribute(me,'thermalRadiance',controls['thermalRadiance'])
   add_color_attribute(me,'thermalColor',controls['thermalColor'])
   add_float_attribute(me,'thermalStrength',controls['thermalStrength'])
  s.frame_set(f);s.cycles.seed=1739+f
  exr=a.out/'frames'/f'{f:04d}.exr';png=a.out/'frames'/f'{f:04d}.png'
  s.render.image_settings.file_format='OPEN_EXR';s.render.image_settings.color_mode='RGBA';s.render.image_settings.color_depth='32';s.render.filepath=str(exr)
  bpy.ops.render.render(write_still=True)
  s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.color_depth='8'
  bpy.data.images['Render Result'].save_render(str(png),scene=s)
  run.receipt(f'render-{f:04d}',[exr,png],frame=f,sourceSHA256=digest(src))
  row={'frame':f,'time':f/a.fps,'sourceSHA256':digest(src),'vertices':len(me.vertices),'triangles':len(me.polygons),
       'temperatureMinK':float(temp.min()),'temperatureMaxK':float(temp.max()),'crustMean':float(controls['crust'].mean()),
       'fracturePotentialMean':float(controls['fracture'].mean()),
       'obsidianMean':float(controls['obsidian'].mean()),
       'reliefMean':float(controls['relief'].mean()),
       'thermalStrengthMean':float(controls['thermalStrength'].mean()),
       'thermalStrengthMax':float(controls['thermalStrength'].max()),
       'wallSeconds':time.perf_counter()-start}
  rows.append(row);atomic_json(a.out/'frames'/f'{f:04d}.json',row);print('LAVA_FRAME',json.dumps(row),flush=True)
  if a.save_blend:bpy.ops.wm.save_as_mainfile(filepath=str(a.out/f'frame-{f:04d}.blend'))
 atomic_json(a.out/'manifest.json',dict(complete=True,frames=len(rows),fps=a.fps,resolution=a.resolution,
   noFrameInterpolation=True,noImageGeneration=True,elapsedSeconds=time.perf_counter()-start,settings=settings))
if __name__=='__main__':main()
