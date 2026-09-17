"""Material-scale detail on the retained MPM and FLIP motion caches."""
from pathlib import Path
import bpy,sys,numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from common import *
from cache_io import fluid_mesh
K=sys.argv[sys.argv.index('--kind')+1];s=setup(secondary_environment=True);rng=np.random.default_rng(441);objects=[]

if K=='metal':
 for light in bpy.data.lights:light.energy*=.42
 mat=scene.material('Brushed stainless steel',(.48,.51,.55),.29,metal=1);n=mat.node_tree.nodes;l=mat.node_tree.links;p=n['Principled BSDF'];p.inputs['Anisotropic'].default_value=.55
 tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(scene.ASSETS/'metal_plate_02_rough_2k.jpg'));tex.image.colorspace_settings.name='Non-Color';scale=n.new('ShaderNodeMath');scale.operation='MULTIPLY_ADD';scale.inputs[1].default_value=.26;scale.inputs[2].default_value=.19;l.new(tex.outputs[0],scale.inputs[0]);l.new(scale.outputs[0],p.inputs['Roughness'])
 for link in list(p.inputs['Roughness'].links):l.remove(link)
 p.inputs['Roughness'].default_value=.26
 uv=n.new('ShaderNodeTexCoord');stretch=n.new('ShaderNodeVectorMath');stretch.operation='MULTIPLY';stretch.inputs[1].default_value=(7,360,1);l.new(uv.outputs['UV'],stretch.inputs[0]);no=noise(mat,1,2,stretch.outputs[0]);bump(mat,no.outputs['Fac'],.000015,.08)
elif K in ['blood','mud']:
 for light in bpy.data.lights:light.energy*=.45
 mat=scene.material('Dense blood' if K=='blood' else 'Wet mineral mud',(.055,.00065,.0014) if K=='blood' else (.032,.017,.007),.17 if K=='blood' else .39,trans=.06 if K=='blood' else 0,ior=1.36 if K=='blood' else 1.333);n=mat.node_tree.nodes;l=mat.node_tree.links;p=n['Principled BSDF'];p.inputs['Coat Weight'].default_value=.045;p.inputs['Coat Roughness'].default_value=.12
 if K=='blood':
  p.inputs['Subsurface Weight'].default_value=.1;p.inputs['Subsurface Radius'].default_value=(.008,.001,.0005);ab=n.new('ShaderNodeVolumeAbsorption');ab.inputs['Color'].default_value=(.18,.001,.002,1);ab.inputs['Density'].default_value=45;l.new(ab.outputs[0],n['Material Output'].inputs['Volume'])
 else:
  no=noise(mat,185,3);bump(mat,no.outputs['Fac'],.0006,.27)
elif K in ['sand','snow']:
 for light in bpy.data.lights:light.energy*=.32 if K=='snow' else .55
 static=np.load(D/'cache'/K/'static.npz');birth=static['birth'];count=len(birth);children=12;volume=float(static['volume']);span=volume**(1/3)
 offsets=rng.uniform(-.5,.5,(count,children,3))*span
 # Each continuum particle contributes a fixed mineral/ice volume. Child
 # grains inherit its affine deformation; this is a render reconstruction,
 # not a claim of an independently solved million-grain contact system.
 weights=np.minimum(1/np.maximum(rng.random((count,children)),.002)**(1/3.1),5)
 rad=weights*(volume*(.62 if K=='sand' else .30)/(4*np.pi/3*np.sum(weights**3,axis=1)))[:,None]**(1/3)
 tags=rng.choice(4,(count,children),p=[.54,.27,.15,.04]);shape=rng.uniform(.72,1.25,(count,children,3))
 shape/=np.prod(shape,axis=2)[:,:,None]**(1/3)
 colors=[(.19,.12,.055),(.31,.235,.14),(.105,.072,.037),(.012,.012,.013)] if K=='sand' else [(.66,.74,.8),(.72,.8,.86),(.6,.71,.79),(.78,.85,.9)]
 mats=[]
 for i,color in enumerate(colors):
  m=scene.material(K+' grain '+str(i),color,.52 if K=='sand' else .43,trans=.025 if K=='sand' else .07,ior=1.54 if K=='sand' else 1.31);p=m.node_tree.nodes['Principled BSDF']
  if K=='snow':p.inputs['Subsurface Weight'].default_value=.16;p.inputs['Subsurface Radius'].default_value=(.004,.005,.006)
  mats.append(m)
else:raise ValueError(K)

for f in selected():
 for ob in objects:scene.remove(ob)
 objects=[]
 if K in ['sand','snow']:
  a=np.load(D/'cache'/K/f'{f:04}.npz');active=birth<=float(a['t']);q=a['p'][active,None,:]+np.einsum('nij,nkj->nki',a['F'][active],offsets[active]);q=q.reshape(-1,3);rr=rad[active].ravel();tt=tags[active].ravel();ss=shape[active].reshape(-1,3)
  assert np.isfinite(q).all()
  if os.environ.get('CYBR_CPU_PROOF')=='1':
   from cpu_stage import visible_grains
   keep=visible_grains(q,rr);q,rr,tt,ss=q[keep],rr[keep],tt[keep],ss[keep]
  for j,mat in enumerate(mats):
   ok=tt==j
   if ok.any():objects.append(instance('Resolved '+K+' grains '+str(j),q[ok],rr[ok],mat,scale=ss[ok],subdivision=1))
 elif K=='metal':
  a=np.load(D/'surface/metal'/f'{f:04}.npz');v=a['v'];fa=a['f']
  if fa.shape[1]==4:fa=np.concatenate([fa[:,[0,1,2]],fa[:,[0,2,3]]])
  from cpu_geometry import seal_boundaries
  ids=np.arange(len(v));uv=np.c_[ids//30/699*3,(ids%15)/14]
  v,fa,uv,caps=seal_boundaries(v,fa,uv)
  ob=mesh('Deformed steel sheet',v,fa,mat);objects.append(ob)
  layer=ob.data.uv_layers.new(name='Steel material');layer.data.foreach_set('uv',uv[fa.ravel()].astype('f4').ravel())
  edge=ob.vertex_groups.new(name='Sheet boundary');edge.add(ids[((ids%15)==0)|((ids%15)==14)|(ids//30==0)|(ids//30==699)].tolist(),1.,'REPLACE')
  bevel=ob.modifiers.new('Physical rolled-edge highlights','BEVEL');bevel.width=.0018;bevel.segments=3;bevel.limit_method='VGROUP';bevel.vertex_group=edge.name
 else:
  v,fa,dp,dr=fluid_mesh(f,K=='mud')
  if len(v):
   if np.sum(v[fa[:,0]]*np.cross(v[fa[:,1]],v[fa[:,2]]))<0:fa=fa[:,[0,2,1]]
   objects.append(mesh('Retained '+K+' liquid surface',v,fa,mat))
  if len(dp):objects.append(instance('Liquid breakup',dp,np.minimum(dr,.035),mat,subdivision=2))
 finish(s,K,f)
