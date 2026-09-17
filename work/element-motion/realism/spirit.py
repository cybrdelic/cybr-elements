import sys,math,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from helpers import *
from mathutils import Matrix
K=sys.argv[sys.argv.index('--kind')+1];s,cam=setup(96);bloom(s,2,-.88);rng=np.random.default_rng(24)

def sculpture():
 with bpy.data.libraries.load(str(R/'assets/marble_bust_01_2k.blend'),link=False) as (a,b):b.objects=[name for name in a.objects if 'LOD0' in name]
 objs=[o for o in b.objects if o and o.type=='MESH']
 if not objs:
  with bpy.data.libraries.load(str(R/'assets/marble_bust_01_2k.blend'),link=False) as (a,b):b.objects=a.objects
  objs=sorted([o for o in b.objects if o and o.type=='MESH'],key=lambda o:len(o.data.vertices),reverse=True)[:1]
 src=max(objs,key=lambda o:len(o.data.vertices));bpy.context.collection.objects.link(src);src.location=(0,0,0);src.rotation_euler=(0,0,0);src.scale=(1,1,1)
 v=np.array([list(v.co) for v in src.data.vertices]);v-=np.array([(v[:,0].min()+v[:,0].max())/2,(v[:,1].min()+v[:,1].max())/2,(v[:,2].min()+v[:,2].max())/2]);v*=2.3/np.ptp(v[:,2]);src.data.vertices.foreach_set('co',v.ravel());src.data.update()
 for image in bpy.data.images:
  path=R/'assets/textures'/Path(image.filepath).name
  if path.exists():image.filepath=str(path);image.reload()
 return src,v

body,v=brandmark();body.location=(.0,0,1.6);body.rotation_euler.z=-.14
for mi,m in enumerate(list(body.data.materials)):
 m=m.copy();body.data.materials[mi]=m;n=m.node_tree.nodes;l=m.node_tree.links;p=next((node for node in n if node.type=='BSDF_PRINCIPLED'),None)
 if not p:continue
 attr=n.new('ShaderNodeAttribute');attr.attribute_name='Purification';ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.004,.006,.008,1);ramp.color_ramp.elements[1].color=(.38,.19,.055,1);l.new(attr.outputs['Fac'],ramp.inputs[0]);l.new(ramp.outputs[0],p.inputs['Base Color']);p.inputs['Metallic'].default_value=.25;p.inputs['Roughness'].default_value=.30
 p.inputs['Emission Color'].default_value=(1,.28,.025,1);front=n.new('ShaderNodeAttribute');front.attribute_name='Front';l.new(front.outputs['Fac'],p.inputs['Emission Strength'])
at=body.data.attributes.new('Purification','FLOAT','POINT');gl=body.data.attributes.new('Front','FLOAT','POINT')
path=np.array([[pose(.08+u*1.6)[0][0],pose(.08+u*1.6)[0][1]] for u in np.linspace(0,1,220)])
world=v+np.array(body.location);delta=world[:,None,[0,2]]-path[None];nearest=np.argmin(np.sum(delta**2,-1),axis=1);arrival=.08+1.6*nearest/219
for f in sorted(selected()):
 t=f/30;age=t-arrival;repair=np.clip(age/.5,0,1);repair=repair*repair*(3-2*repair);at.data.foreach_set('value',repair);gl.data.foreach_set('value',np.exp(-((age-.16)/.14)**2)*1.6);body.data.update();finish(s,K,f)
