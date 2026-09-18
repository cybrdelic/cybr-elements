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
 p.add_argument('--frames',type=int,default=60);p.add_argument('--fps',type=int,default=24)
 p.add_argument('--resolution',type=int,nargs=2,default=[960,540]);p.add_argument('--samples',type=int,default=96)
 p.add_argument('--threads',type=int,default=2);p.add_argument('--frame',type=int)
 p.add_argument('--exposure',type=float,default=.1)
 p.add_argument('--view',choices=['oblique','front','overhead'],default='oblique')
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
 p.inputs['IOR'].default_value=1.48
 p.inputs['Coat Roughness'].default_value=.18
 nodes=lava.node_tree.nodes;links=lava.node_tree.links
 base=attribute(nodes,'baseColor')
 rough_base=attribute(nodes,'roughnessBase')
 coat=attribute(nodes,'coatWeight')
 thermal=attribute(nodes,'thermalRadiance')
 rest=attribute(nodes,'materialCoordinates')
 fracture=attribute(nodes,'fracturePotential')
 crust=attribute(nodes,'crustAmount')
 links.new(base.outputs['Color'],p.inputs['Base Color'])
 links.new(coat.outputs['Fac'],p.inputs['Coat Weight'])
 links.new(thermal.outputs['Color'],p.inputs['Emission Color'])
 p.inputs['Emission Strength'].default_value=1.0

 macro=nodes.new('ShaderNodeTexNoise');macro.noise_dimensions='3D';macro.label='advected crust macrostructure'
 macro.inputs['Scale'].default_value=23.;macro.inputs['Detail'].default_value=5.2
 macro.inputs['Roughness'].default_value=.72;macro.inputs['Distortion'].default_value=.17
 links.new(rest.outputs['Vector'],macro.inputs['Vector'])
 micro=nodes.new('ShaderNodeTexNoise');micro.noise_dimensions='3D';micro.label='advected vesicle microstructure'
 micro.inputs['Scale'].default_value=185.;micro.inputs['Detail'].default_value=4.5
 micro.inputs['Roughness'].default_value=.78;micro.inputs['Distortion'].default_value=.08
 links.new(rest.outputs['Vector'],micro.inputs['Vector'])

 cells=nodes.new('ShaderNodeTexVoronoi');cells.voronoi_dimensions='3D';cells.feature='DISTANCE_TO_EDGE';cells.distance='EUCLIDEAN'
 cells.label='damage-gated sub-grid crust edges';cells.inputs['Scale'].default_value=39.
 links.new(rest.outputs['Vector'],cells.inputs['Vector'])
 edge=nodes.new('ShaderNodeMapRange');edge.clamp=True;edge.interpolation_type='SMOOTHERSTEP';edge.label='thin cellular edges'
 edge.inputs['From Min'].default_value=.012;edge.inputs['From Max'].default_value=.095
 edge.inputs['To Min'].default_value=1.;edge.inputs['To Max'].default_value=0.
 links.new(cells.outputs['Distance'],edge.inputs['Value'])
 fracture_edge=math_node(nodes,'MULTIPLY',label='resolved damage × sub-grid edge')
 links.new(fracture.outputs['Fac'],fracture_edge.inputs[0]);links.new(edge.outputs['Result'],fracture_edge.inputs[1])

 macro_gain=nodes.new('ShaderNodeMapRange');macro_gain.clamp=True
 macro_gain.inputs['From Min'].default_value=.12;macro_gain.inputs['From Max'].default_value=.88
 macro_gain.inputs['To Min'].default_value=.72;macro_gain.inputs['To Max'].default_value=1.24
 links.new(macro.outputs['Fac'],macro_gain.inputs['Value'])
 base_mod=nodes.new('ShaderNodeMixRGB');base_mod.blend_type='MULTIPLY';base_mod.inputs['Fac'].default_value=1.
 links.new(base.outputs['Color'],base_mod.inputs[1]);links.new(macro_gain.outputs['Result'],base_mod.inputs[2])
 fracture_dark=nodes.new('ShaderNodeMixRGB');fracture_dark.blend_type='MULTIPLY'
 links.new(fracture_edge.outputs[0],fracture_dark.inputs['Fac']);links.new(base_mod.outputs['Color'],fracture_dark.inputs[1])
 fracture_dark.inputs[2].default_value=(.16,.18,.20,1.)
 links.new(fracture_dark.outputs['Color'],p.inputs['Base Color'])

 micro_center=math_node(nodes,'SUBTRACT',b=.5,label='micro centered');links.new(micro.outputs['Fac'],micro_center.inputs[0])
 micro_amp=math_node(nodes,'MULTIPLY',b=.12,label='micro roughness amplitude');links.new(micro_center.outputs[0],micro_amp.inputs[0])
 rough_add=math_node(nodes,'ADD',label='phase roughness + microstructure');links.new(rough_base.outputs['Fac'],rough_add.inputs[0]);links.new(micro_amp.outputs[0],rough_add.inputs[1])
 fracture_rough=math_node(nodes,'MULTIPLY',b=.055,label='fracture roughness');links.new(fracture_edge.outputs[0],fracture_rough.inputs[0])
 rough_total=math_node(nodes,'ADD');links.new(rough_add.outputs[0],rough_total.inputs[0]);links.new(fracture_rough.outputs[0],rough_total.inputs[1])
 rough_clamp=nodes.new('ShaderNodeClamp');rough_clamp.inputs['Min'].default_value=.16;rough_clamp.inputs['Max'].default_value=.98
 links.new(rough_total.outputs[0],rough_clamp.inputs['Value']);links.new(rough_clamp.outputs['Result'],p.inputs['Roughness'])

 macro_bump=nodes.new('ShaderNodeBump');macro_bump.label='cooled skin relief';macro_bump.inputs['Strength'].default_value=.28;macro_bump.inputs['Distance'].default_value=.0032
 links.new(macro.outputs['Fac'],macro_bump.inputs['Height'])
 macro_strength=math_node(nodes,'MULTIPLY',a=.36,label='crust relief weight');links.new(crust.outputs['Fac'],macro_strength.inputs[1]);links.new(macro_strength.outputs[0],macro_bump.inputs['Strength'])
 micro_bump=nodes.new('ShaderNodeBump');micro_bump.label='vesicle-scale relief';micro_bump.inputs['Strength'].default_value=.24;micro_bump.inputs['Distance'].default_value=.00065
 links.new(micro.outputs['Fac'],micro_bump.inputs['Height']);links.new(macro_bump.outputs['Normal'],micro_bump.inputs['Normal'])
 fissure_bump=nodes.new('ShaderNodeBump');fissure_bump.label='damage-gated crease';fissure_bump.invert=True;fissure_bump.inputs['Strength'].default_value=.50;fissure_bump.inputs['Distance'].default_value=.0015
 links.new(fracture_edge.outputs[0],fissure_bump.inputs['Height']);links.new(micro_bump.outputs['Normal'],fissure_bump.inputs['Normal']);links.new(fissure_bump.outputs['Normal'],p.inputs['Normal'])

 coat_rough=math_node(nodes,'MULTIPLY',b=.34,label='coat roughness from phase');links.new(rough_clamp.outputs['Result'],coat_rough.inputs[0]);links.new(coat_rough.outputs[0],p.inputs['Coat Roughness'])
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


def main():
 a=parser();wait_for(a.surface/'run.json',timeout=a.wait_timeout);surface_settings=json.loads((a.surface/'run.json').read_text())['settings'];floor_height=float(surface_settings['floor']);bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
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
 bg=s.world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(.055,.065,.082,1);bg.inputs['Strength'].default_value=.035
 bpy.ops.object.camera_add();camera=bpy.context.object;s.camera=camera
 target=(0.,0.,.335)
 positions={'oblique':(.82,-2.65,1.03),'front':(0.,-3.,.5),'overhead':(.62,-1.75,1.8)}
 camera.location=positions[a.view];camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
 camera.data.type='ORTHO';camera.data.ortho_scale=1.65;camera.data.clip_start=.01;camera.data.clip_end=30
 area('Large neutral key',(-.55,-.75,1.45),42,(.90,.93,1.),1.15,target)
 area('Grazing rim',(.65,.6,1.1),62,(.83,.88,.97),.88,target)
 area('Soft front fill',(-.3,-1.,.55),9,(1.,.90,.78),1.35,target)
 floor,fp=principled('Fine basalt stage');fp.inputs['Base Color'].default_value=(.012,.014,.017,1);fp.inputs['Roughness'].default_value=.82
 n=floor.node_tree.nodes;l=floor.node_tree.links
 tc=n.new('ShaderNodeTexCoord');noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=95;noise.inputs['Detail'].default_value=4
 l.new(tc.outputs['Object'],noise.inputs['Vector']);bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.21;bump.inputs['Distance'].default_value=.0014
 l.new(noise.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],fp.inputs['Normal'])
 bpy.ops.mesh.primitive_plane_add(size=8,location=(0,0,floor_height));bpy.context.object.data.materials.append(floor)
 lava=build_lava_material()
 settings={'device':'CPU','engine':'Cycles','blender':bpy.app.version_string,'resolution':a.resolution,'samples':a.samples,
  'adaptiveThreshold':.018,'denoiser':'OpenImageDenoISE','fps':a.fps,'frames':a.frames,'frame':a.frame,
  'floor':floor_height,'exposure':a.exposure,'view':a.view,'viewTransform':'AgX','look':'Medium High Contrast','motionBlur':False,
  'material':'resolved temperature/damage phase controls + Planck-band emission + transported-coordinate multiscale crust relief',
  'subgridDisclosure':'noise/voronoi are BSDF microstructure anchored to material coordinates; damage gates crease relief; no resolved crack geometry is claimed'}
 run=RunIdentity(a.out,settings,{'surfaceRun':a.surface/'run.json','entry':Path(__file__),'materialControls':Path(__file__).parent/'elements_core/lava_material.py'})
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
   add_float_attribute(me,'roughnessBase',controls['roughness'])
   add_float_attribute(me,'coatWeight',controls['coat'])
   add_vector_attribute(me,'materialCoordinates',data['rest'])
   add_color_attribute(me,'baseColor',controls['baseColor'])
   add_color_attribute(me,'thermalRadiance',controls['thermalRadiance'])
  s.frame_set(f);s.cycles.seed=1739+f
  exr=a.out/'frames'/f'{f:04d}.exr';png=a.out/'frames'/f'{f:04d}.png'
  s.render.image_settings.file_format='OPEN_EXR';s.render.image_settings.color_mode='RGBA';s.render.image_settings.color_depth='32';s.render.filepath=str(exr)
  bpy.ops.render.render(write_still=True)
  s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.color_depth='8'
  bpy.data.images['Render Result'].save_render(str(png),scene=s)
  run.receipt(f'render-{f:04d}',[exr,png],frame=f,sourceSHA256=digest(src))
  row={'frame':f,'time':f/a.fps,'sourceSHA256':digest(src),'vertices':len(me.vertices),'triangles':len(me.polygons),
       'temperatureMinK':float(temp.min()),'temperatureMaxK':float(temp.max()),'crustMean':float(controls['crust'].mean()),
       'fracturePotentialMean':float(controls['fracture'].mean()),'wallSeconds':time.perf_counter()-start}
  rows.append(row);atomic_json(a.out/'frames'/f'{f:04d}.json',row);print('LAVA_FRAME',json.dumps(row),flush=True)
  if a.save_blend:bpy.ops.wm.save_as_mainfile(filepath=str(a.out/f'frame-{f:04d}.blend'))
 atomic_json(a.out/'manifest.json',dict(complete=True,frames=len(rows),fps=a.fps,resolution=a.resolution,
   noFrameInterpolation=True,noImageGeneration=True,elapsedSeconds=time.perf_counter()-start,settings=settings))
if __name__=='__main__':main()
