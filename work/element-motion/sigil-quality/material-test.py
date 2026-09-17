"""Material-specific native-resolution tests. These are stills, not completed simulations."""
from pathlib import Path
import sys,time,json,hashlib
import numpy as np
import bpy
from mathutils import Vector
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R.parent/'dynamics'));import scene
args=sys.argv[sys.argv.index('--')+1:];K=args[args.index('--kind')+1]
V=args[args.index('--variant')+1] if '--variant' in args else '01'
view=args[args.index('--view')+1] if '--view' in args else 'wide'
T=float(args[args.index('--time')+1]) if '--time' in args else 8.
native_frame=int(args[args.index('--native-frame')+1]) if '--native-frame' in args else None
geometry_path=R/'native-liquid-01-v2'/f'particle-surface-{native_frame:04}.npz' if native_frame is not None else R/f'geometry-{V}.npz'
data=np.load(geometry_path);v=data['v'].copy();faces=data['faces'];normal=data['normal'];born=data['born']
s=scene.setup(256);s.cycles.samples=256;s.cycles.adaptive_threshold=.008;s.cycles.use_adaptive_sampling=True
s.view_settings.exposure=-.6;s.render.resolution_x=1920;s.render.resolution_y=1080
s.camera.location=(.6 if view=='macro' else 0,-15,2.35);s.camera.data.ortho_scale=4.8 if view=='macro' else 11.4
for light in bpy.data.lights:light.energy*=.6
# A photographic lighting environment contributes to reflections only; all
# unobstructed and transmitted backdrop rays see the black studio.
wn=s.world.node_tree.nodes;wl=s.world.node_tree.links
ray=wn.new('ShaderNodeLightPath');env=wn.new('ShaderNodeBackground');tex=wn.new('ShaderNodeTexEnvironment')
tex.image=bpy.data.images.load(str(scene.ASSETS/'studio_small_08_2k.exr'));env.inputs['Strength'].default_value=.30
mix=wn.new('ShaderNodeMixShader');wl.new(tex.outputs[0],env.inputs[0]);wl.new(ray.outputs['Is Reflection Ray'],mix.inputs[0]);wl.new(wn.get('Background').outputs[0],mix.inputs[1]);wl.new(env.outputs[0],mix.inputs[2]);wl.new(mix.outputs[0],wn.get('World Output').inputs[0])

def mesh(name,verts,triangles,material,smooth=True):
    me=bpy.data.meshes.new(name);me.vertices.add(len(verts));me.vertices.foreach_set('co',np.asarray(verts,dtype='f4').ravel())
    me.loops.add(triangles.size);me.loops.foreach_set('vertex_index',np.asarray(triangles,dtype='i4').ravel())
    me.polygons.add(len(triangles));me.polygons.foreach_set('loop_start',np.arange(0,triangles.size,3,dtype='i4'));me.polygons.foreach_set('loop_total',np.full(len(triangles),3,dtype='i4'))
    me.polygons.foreach_set('use_smooth',np.full(len(triangles),smooth));me.materials.append(material);me.update()
    ob=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(ob);return ob

def pores(mat,scale,distance,strength):
    n=mat.node_tree.nodes;l=mat.node_tree.links;no=n.new('ShaderNodeTexNoise');no.inputs['Scale'].default_value=scale;no.inputs['Detail'].default_value=3
    bump=n.new('ShaderNodeBump');bump.inputs['Distance'].default_value=distance;bump.inputs['Strength'].default_value=strength
    l.new(no.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs[0],n.get('Principled BSDF').inputs['Normal'])

if K=='blood':
    # Deep diffuse body with short scattering distances; not a clear red coat.
    mat=scene.material('Dense absorbing liquid',(.027,.00045,.00075),.21,trans=.035,ior=1.36)
    p=mat.node_tree.nodes.get('Principled BSDF');p.inputs['Coat Weight'].default_value=.035;p.inputs['Coat Roughness'].default_value=.17
    p.inputs['Subsurface Weight'].default_value=.13;p.inputs['Subsurface Radius'].default_value=(.008,.0012,.00055)
    ab=mat.node_tree.nodes.new('ShaderNodeVolumeAbsorption');ab.inputs['Color'].default_value=(.22,.001,.002,1);ab.inputs['Density'].default_value=70;mat.node_tree.links.new(ab.outputs[0],mat.node_tree.nodes.get('Material Output').inputs['Volume'])
    mesh('Continuous dense liquid surface',v,faces,mat)
elif K=='ice':
    mat=scene.material('Clear ice body',(.97,.989,1),.035,trans=1,ior=1.31)
    n=mat.node_tree.nodes;l=mat.node_tree.links;ab=n.new('ShaderNodeVolumeAbsorption');ab.inputs['Color'].default_value=(.70,.88,.98,1);ab.inputs['Density'].default_value=.45;l.new(ab.outputs[0],n.get('Material Output').inputs['Volume'])
    pores(mat,210,.00013,.12)
    coordinate=n.new('ShaderNodeTexCoord');separate=n.new('ShaderNodeSeparateXYZ');l.new(coordinate.outputs['Object'],separate.inputs[0]);absolute=n.new('ShaderNodeMath');absolute.operation='ABSOLUTE';l.new(separate.outputs['Y'],absolute.inputs[0]);core=n.new('ShaderNodeMapRange');core.inputs['From Min'].default_value=.015;core.inputs['From Max'].default_value=.11;core.inputs['To Min'].default_value=1;core.inputs['To Max'].default_value=0;l.new(absolute.outputs[0],core.inputs[0])
    cloud=n.new('ShaderNodeTexNoise');cloud.inputs['Scale'].default_value=11;cloud.inputs['Detail'].default_value=2;l.new(coordinate.outputs['Object'],cloud.inputs['Vector']);cluster=n.new('ShaderNodeValToRGB');cluster.color_ramp.elements[0].position=.48;cluster.color_ramp.elements[1].position=.70;l.new(cloud.outputs['Fac'],cluster.inputs[0]);density=n.new('ShaderNodeMath');density.operation='MULTIPLY';l.new(core.outputs[0],density.inputs[0]);l.new(cluster.outputs[0],density.inputs[1]);strength=n.new('ShaderNodeMath');strength.operation='MULTIPLY';strength.inputs[1].default_value=20;l.new(density.outputs[0],strength.inputs[0]);scatter=n.new('ShaderNodeVolumeScatter');scatter.inputs['Anisotropy'].default_value=.12;l.new(strength.outputs[0],scatter.inputs['Density']);add=n.new('ShaderNodeAddShader');l.new(ab.outputs[0],add.inputs[0]);l.new(scatter.outputs[0],add.inputs[1]);l.new(add.outputs[0],n.get('Material Output').inputs['Volume'])
    mesh('Optically clear frozen surface',v,faces,mat)
    # Sparse embedded air interfaces with a long-tailed radius distribution.
    source=np.load(R.parent/'sigils'/f'source-{V}.npz');points=source['particles'];rng=np.random.default_rng(728)
    chosen=rng.choice(len(points),1900,replace=False);points=points[chosen].copy();points[:,1]*=1.35
    radii=np.clip(rng.lognormal(np.log(.001),.72,len(points)),.00025,.007)
    air=scene.material('Embedded air boundaries',(.99,.99,1),.07,trans=1,ior=1/1.31)
    scene.points('Embedded elongated microbubbles',points,radii,air,scale=np.tile([.65,.75,1.7],(len(points),1)))
elif K=='lava':
    sys.path.insert(0,str(R));from basalt import build
    for light in bpy.data.lights:light.energy*=.4
    env.inputs['Strength'].default_value=.12
    build(v,faces,normal,born,T,mesh,scene)
    scene.glare(s,2.5,-.96)
else:raise ValueError(K)
out=R/'frames';out.mkdir(exist_ok=True);path=out/(f'native-particle-{native_frame:04}-{K}.jpg' if native_frame is not None else f'{K}-{V}-{view}-{T:g}-r3.jpg');s.render.filepath=str(path)
start=time.time();bpy.ops.render.render(write_still=True)
(out/f'{path.stem}.json').write_text(json.dumps({'kind':K,'variant':V,'view':view,'time':T,'width':1920,'height':1080,'samples':256,'seconds':time.time()-start,'geometrySha256':hashlib.sha256(geometry_path.read_bytes()).hexdigest(),'status':'Early density-surface diagnostic from cached FLIP particles; final meshing pending' if native_frame is not None else 'Material look-development still; no new simulation claim'},indent=2))
print('FRESH MATERIAL FRAME',str(path),flush=True)
