from pathlib import Path
import bpy,sys,json,time,os,numpy as np
from mathutils import Vector
R=Path(__file__).resolve().parent;D=R.parent/'dynamics';sys.path.insert(0,str(D))
import scene

def setup(secondary_environment=False):
 cpu=os.environ.get('CYBR_CPU_PROOF')=='1'
 if (R/'cpu-only-hold.json').exists() and not cpu:raise RuntimeError('GPU and full-render work is paused by the user; use the CPU proof harness')
 if cpu:
  import cpu_stage
  s=cpu_stage.setup()
 else:s=scene.setup(192)
 s.cycles.adaptive_threshold=.008;s.view_settings.exposure=-.35
 s.cycles.max_bounces=20;s.cycles.transmission_bounces=16;s.cycles.glossy_bounces=10
 for light in bpy.data.lights:light.energy*=.68
 w=s.world.node_tree;n=w.nodes;l=w.links;ray=n.new('ShaderNodeLightPath');tex=n.new('ShaderNodeTexEnvironment');tex.image=bpy.data.images.load(str(scene.ASSETS/'studio_small_08_2k.exr'));env=n.new('ShaderNodeBackground');env.inputs[1].default_value=.28
 mix=n.new('ShaderNodeMixShader');l.new(tex.outputs[0],env.inputs[0]);l.new(ray.outputs['Is Reflection Ray'],mix.inputs[0]);l.new(n['Background'].outputs[0],mix.inputs[1]);l.new(env.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],n['World Output'].inputs[0])
 if secondary_environment:
  # Match the accepted water film's soft off-camera lighting. Primary camera
  # rays remain exactly black; refraction sees a controlled studio gradient.
  tc=n.new('ShaderNodeTexCoord');dot=n.new('ShaderNodeVectorMath');dot.operation='DOT_PRODUCT';dot.inputs[1].default_value=(.55,.15,.80);l.new(tc.outputs['Normal'],dot.inputs[0]);remap=n.new('ShaderNodeMapRange');remap.inputs['From Min'].default_value=-1;remap.inputs['From Max'].default_value=1;l.new(dot.outputs['Value'],remap.inputs[0]);ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1])
  for i,(pos,color) in enumerate([(0,(.015,.02,.025)),(.28,(.025,.03,.035)),(.44,(.18,.30,.36)),(.53,(.012,.018,.022)),(.70,(.16,.23,.27)),(.86,(.10,.12,.14)),(1,(.02,.025,.03))]):
   e=ramp.color_ramp.elements[0] if i==0 else ramp.color_ramp.elements.new(pos);e.position=pos;e.color=(*color,1)
  l.new(remap.outputs[0],ramp.inputs[0]);gradient=n.new('ShaderNodeBackground');gradient.inputs[1].default_value=.8;l.new(ramp.outputs[0],gradient.inputs[0]);l.new(gradient.outputs[0],mix.inputs[1]);camera=n.new('ShaderNodeMixShader');l.new(ray.outputs['Is Camera Ray'],camera.inputs[0]);l.new(mix.outputs[0],camera.inputs[1]);l.new(n['Background'].outputs[0],camera.inputs[2]);l.new(camera.outputs[0],n['World Output'].inputs[0])
 return s

def mesh(name,v,f,mat,smooth=True,coord=None):
 assert f.ndim==2 and f.shape[1]==3,(name,'triangulate all face corners before building a mesh')
 me=bpy.data.meshes.new(name);me.vertices.add(len(v));me.vertices.foreach_set('co',np.asarray(v,dtype='f4').ravel());me.loops.add(f.size);me.loops.foreach_set('vertex_index',np.asarray(f,dtype='i4').ravel());me.polygons.add(len(f));me.polygons.foreach_set('loop_start',np.arange(0,f.size,3,dtype='i4'));me.polygons.foreach_set('loop_total',np.full(len(f),3,dtype='i4'));me.polygons.foreach_set('use_smooth',np.full(len(f),smooth));me.materials.append(mat);me.update()
 if coord is not None:
  at=me.attributes.new('material_position','FLOAT_VECTOR','POINT');at.data.foreach_set('vector',np.asarray(coord,dtype='f4').ravel())
 ob=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(ob);return ob

def instance(name,p,r,mat,scale=None,inward=False,subdivision=2):
 ob=scene.points(name,p,r,mat,scale=scale);g=ob.modifiers[0].node_group;ico=next(n for n in g.nodes if n.bl_idname=='GeometryNodeMeshIcoSphere');ico.inputs['Subdivisions'].default_value=subdivision
 source=ico.outputs['Mesh'];sm=next(n for n in g.nodes if n.bl_idname=='GeometryNodeSetMaterial')
 if inward:
  flip=g.nodes.new('GeometryNodeFlipFaces');g.links.new(source,flip.inputs['Mesh']);source=flip.outputs['Mesh']
 smooth=g.nodes.new('GeometryNodeSetShadeSmooth');g.links.new(source,smooth.inputs['Geometry']);g.links.new(smooth.outputs[0],sm.inputs['Geometry']);return ob

def attr(mat,name='material_position'):
 n=mat.node_tree.nodes;node=n.new('ShaderNodeAttribute');node.attribute_name=name;return node

def noise(mat,scale,detail=3,coordinate=None):
 node=mat.node_tree.nodes.new('ShaderNodeTexNoise');node.inputs['Scale'].default_value=scale;node.inputs['Detail'].default_value=detail
 if coordinate is not None:mat.node_tree.links.new(coordinate,node.inputs['Vector'])
 return node

def bump(mat,height,distance,strength):
 n=mat.node_tree.nodes;l=mat.node_tree.links;b=n.new('ShaderNodeBump');b.inputs['Distance'].default_value=distance;b.inputs['Strength'].default_value=strength;l.new(height,b.inputs['Height']);l.new(b.outputs[0],n['Principled BSDF'].inputs['Normal']);return b

def selected():
 if '--frames' in sys.argv:return [int(x) for x in sys.argv[sys.argv.index('--frames')+1].split(',')]
 return list(range(120)) if '--full' in sys.argv else [30,45,65,90]

def finish(s,k,f):
 if os.environ.get('CYBR_CPU_PROOF')=='1':
  import cpu_stage
  return cpu_stage.finish(s,k,f)
 if (R/'cpu-only-hold.json').exists():raise RuntimeError('Full rendering is paused by the CPU-only contract')
 out=R/'frames'/k;out.mkdir(parents=True,exist_ok=True);s.frame_set(f+1);s.render.filepath=str(out/f'{f:04}.jpg');start=time.time();bpy.ops.render.render(write_still=True)
 print('FRAME',k,f,round(time.time()-start,2),flush=True)
