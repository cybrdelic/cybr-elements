"""Distinct lava crust, clear ice interiors and surface-attached wet foam."""
import sys
from pathlib import Path
import numpy as np,bpy
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R))
from common import *
K=sys.argv[sys.argv.index('--kind')+1];s=setup(secondary_environment=True);objects=[]
if K=='foam':s.render.use_persistent_data=False

def normals(v,f):
 n=np.zeros_like(v);fn=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
 for j in range(3):np.add.at(n,f[:,j],fn)
 return n/np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-8)

def subdivide(v,f,attributes):
 edges=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]);edges=np.sort(edges,axis=1);unique,inverse=np.unique(edges,axis=0,return_inverse=True);mid=inverse.reshape(3,-1).T+len(v)
 values=[np.concatenate([q,(q[unique[:,0]]+q[unique[:,1]])*.5]) for q in [v,*attributes]]
 faces=np.concatenate([np.c_[f[:,0],mid[:,0],mid[:,2]],np.c_[mid[:,0],f[:,1],mid[:,1]],np.c_[mid[:,2],mid[:,1],f[:,2]],mid])
 return values[0],faces,values[1:]

def irregular(p,scale,seed=31):
 rng=np.random.default_rng(seed);axes=rng.normal(size=(9,3));axes/=np.linalg.norm(axes,axis=1)[:,None];phase=rng.uniform(0,6.28,9);weights=np.linspace(1,.3,9)
 return (np.sin(p@axes.T*scale*6.28+phase)*weights).sum(1)/weights.sum()

def transmitted_shadows(mat):
 # Cycles treats refracting boundaries as opaque to direct shadow rays.
 # A transmission approximation lets the broad studio lights reach interiors;
 # camera and reflection rays still use the refractive surface.
 n=mat.node_tree.nodes;l=mat.node_tree.links;ray=n.new('ShaderNodeLightPath');clear=n.new('ShaderNodeBsdfTransparent');clear.inputs[0].default_value=(.91,.96,.98,1);mix=n.new('ShaderNodeMixShader');l.new(ray.outputs['Is Shadow Ray'],mix.inputs[0]);l.new(n['Principled BSDF'].outputs[0],mix.inputs[1]);l.new(clear.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],n['Material Output'].inputs['Surface'])

if K=='lava':
 for light in bpy.data.lights:light.energy*=.30
 core=scene.material('Incandescent exposed liquid',(.012,.002,.0004),.48)
 n=core.node_tree.nodes;l=core.node_tree.links;p=n['Principled BSDF'];at=attr(core,'heat');temp=n.new('ShaderNodeMath');temp.operation='MULTIPLY_ADD';temp.inputs[1].default_value=550;temp.inputs[2].default_value=900;l.new(at.outputs['Fac'],temp.inputs[0]);bb=n.new('ShaderNodeBlackbody');l.new(temp.outputs[0],bb.inputs[0]);l.new(bb.outputs[0],p.inputs['Emission Color']);p.inputs['Emission Strength'].default_value=1.25
 p.inputs['Emission Strength'].default_value=.23
 co=attr(core);no=noise(core,32,3,co.outputs['Vector']);bump(core,no.outputs['Fac'],.006,.45)
 crust=scene.material('Continuous basalt skin',(.024,.019,.015),.47)
 co=attr(crust);no=noise(crust,53,4,co.outputs['Vector']);bump(crust,no.outputs['Fac'],.007,.55)
 scene.glare(s,1.5,-.94)
elif K=='ice':
 core=scene.material('Clear ice with internal air',(.975,.991,1),.022,trans=1,ior=1.31)
 n=core.node_tree.nodes;l=core.node_tree.links;co=attr(core);no=noise(core,155,2,co.outputs['Vector']);bump(core,no.outputs['Fac'],.00016,.16)
 absorb=n.new('ShaderNodeVolumeAbsorption');absorb.inputs['Color'].default_value=(.73,.9,.975,1);absorb.inputs['Density'].default_value=.35
 tex=n.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=22;tex.inputs['Detail'].default_value=3
 ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.55;ramp.color_ramp.elements[1].position=.75;l.new(tex.outputs['Fac'],ramp.inputs[0]);mult=n.new('ShaderNodeMath');mult.operation='MULTIPLY';mult.inputs[1].default_value=3;l.new(ramp.outputs[0],mult.inputs[0]);scatter=n.new('ShaderNodeVolumeScatter');scatter.inputs['Anisotropy'].default_value=.25;l.new(mult.outputs[0],scatter.inputs['Density']);add=n.new('ShaderNodeAddShader');l.new(absorb.outputs[0],add.inputs[0]);l.new(scatter.outputs[0],add.inputs[1]);l.new(add.outputs[0],n['Material Output'].inputs['Volume'])
 air=scene.material('Inward-facing ice air cavities',(.995,.998,1),.036,trans=1,ior=1.31)
 fissure=scene.material('Internal fracture interfaces',(.76,.86,.91),.24,trans=.55,ior=1.31)
 inner=bpy.data.materials.new('Light-scattering frozen core');inner.use_nodes=True;n=inner.node_tree.nodes;l=inner.node_tree.links;n.remove(n['Principled BSDF']);clear=n.new('ShaderNodeBsdfTransparent');l.new(clear.outputs[0],n['Material Output'].inputs['Surface']);scatter=n.new('ShaderNodeVolumeScatter');scatter.inputs['Color'].default_value=(.72,.88,.97,1);scatter.inputs['Density'].default_value=3.0;scatter.inputs['Anisotropy'].default_value=.3;l.new(scatter.outputs[0],n['Material Output'].inputs['Volume'])
elif K=='foam':
 for light in bpy.data.lights:light.energy*=.22
 core=scene.material('Water beneath the foam',(.97,.991,1),.018,trans=1,ior=1.333)
 foam=scene.material('Connected wet microfoam',(.60,.66,.67),.26,ior=1.333);p=foam.node_tree.nodes['Principled BSDF'];p.inputs['Subsurface Weight'].default_value=.14;p.inputs['Subsurface Radius'].default_value=(.012,.016,.018);p.inputs['Coat Weight'].default_value=.2;p.inputs['Coat Roughness'].default_value=.025
 no=noise(foam,240,2);bump(foam,no.outputs['Fac'],.0018,.8)
 film=scene.material('Water film around gas cells',(.97,.991,1),.025,trans=.88,ior=1.333);p=film.node_tree.nodes['Principled BSDF'];p.inputs['Coat Weight'].default_value=.1
else:raise ValueError(K)
if K=='ice':
 for mat in [core,air,fissure]:transmitted_shadows(mat)
if K=='foam':
 for mat in [core,film]:transmitted_shadows(mat)

for f in selected():
 for ob in objects:scene.remove(ob)
 objects=[];a=np.load(R/'data'/K/f'{f:04}.npz');v=a['v'];fa=a['f']
 if len(v):
  # Density-isosurface exports use inward winding. Closed optical boundaries
  # must face outward, or refraction is evaluated from the wrong medium.
  signed_volume=np.sum(v[fa[:,0]]*np.cross(v[fa[:,1]],v[fa[:,2]]))/6
  if signed_volume<0:fa=fa[:,[0,2,1]]
  coord=a['coord'] if 'coord' in a else v
  ob=mesh('Transported '+K+' body',v,fa,core,coord=coord);objects.append(ob)
  if K!='foam':
   sub=ob.modifiers.new('Resolved smooth surface','SUBSURF');sub.levels=1;sub.render_levels=1
  if K=='lava':
   at=ob.data.attributes.new('heat','FLOAT','POINT');at.data.foreach_set('value',a['heat'])
   vv,ff,attrs=subdivide(v,fa,[coord,a['heat']]);vv,ff,attrs=subdivide(vv,ff,attrs);cc,heat=attrs;nn=normals(vv,ff)
   fracture=(.95-heat)*3.6+irregular(cc,8)*.6+irregular(cc,37,52)*.12
   keep=np.mean(fracture[ff],axis=1)>.075
   vv=vv+nn*(.004+.003*irregular(cc,38))[:,None]
   if keep.any():
    skin=mesh('Ruptured coherent cooling skin',vv,ff[keep],crust,coord=cc);objects.append(skin);solid=skin.modifiers.new('Finite crust thickness','SOLIDIFY');solid.thickness=.003;solid.offset=0
  elif K=='ice':
   nn=normals(v,fa);inside=a['innerfaces'][:,[0,2,1]] if signed_volume<0 else a['innerfaces'];innerbody=mesh('Frozen core beneath the clear shell',v-nn*.008,inside,inner);objects.append(innerbody)
   state=np.load(D/'cache/ice'/f'{f:04}.npz');pp=state['p'];phase=state['phase'];ids=np.arange(len(pp));ok=(ids%11==0)&(phase>.35);pts=pp[ok];rng=np.random.default_rng(89)
   if len(pts):
    rad=np.clip(rng.lognormal(np.log(.0013),.7,len(pts)),.0004,.0045);objects.append(instance('Embedded air voids',pts,rad,air,scale=np.tile([.6,.85,2.3],(len(pts),1)),inward=True))
   ok=(ids%97==0)&(phase>.48);pts=pp[ok]
   if len(pts):
    # Thin internal fracture planes, distinct from a diffuse outer frost coat.
    rad=.007+.013*(np.sin(ids[ok]*.717)*.5+.5)**3;objects.append(instance('Internal fracture planes',pts,rad,fissure,scale=np.tile([1,.018,1.7],(len(pts),1)),subdivision=1))
  elif K=='foam':
   cover=a['coverage'];nn=a['normal'];keep=np.mean(cover[fa],axis=1)>.42
   if keep.any():objects.append(mesh('Contiguous aerated foam patches',v-nn*.002,fa[keep],foam))
   from cpu_geometry import packed_surface_cells
   ids=packed_surface_cells(a['p'],a['r'],a['id']);pts=a['p'][ids];rad=a['r'][ids]
   # Former reconstruction multiplied radii by 1.9 and let 84% of cells
   # strongly overlap. Preserve physical radius and resolve the larger cells;
   # the connected wet body handles subpixel gas instead of enlarged beads.
   resolved=rad>.006
   if resolved.any():objects.append(instance('Packed gas cell films',pts[resolved],rad[resolved],film,subdivision=2))
 finish(s,K,f)
