import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from scene import *
K=sys.argv[sys.argv.index('--kind')+1] if '--kind' in sys.argv else 'plants';s=setup(96)
data=np.load(R/'cache/plants/rods.npz');info=json.loads((R/'cache/plants/structure.json').read_text(encoding='utf-8'));P=data['p'];birth=data['birth'];rest=data['rest'];radii=data['radii']
with bpy.data.libraries.load(str(ASSETS/'nettle_plant_2k.blend'),link=False) as (a,b):b.objects=[name for name in a.objects if name.endswith('LOD0')]
sources=[o for o in b.objects if o.type=='MESH']
for image in bpy.data.images:
    p=ASSETS/'textures'/Path(image.filepath).name
    if p.exists():image.filepath=str(p);image.reload()
shoots=[]
def attach_repair(tree):
    for node in list(tree.nodes):
        if node.type=='GROUP':attach_repair(node.node_tree)
        if node.type=='BSDF_PRINCIPLED':
            at=tree.nodes.get('Repair field')
            if at is None:at=tree.nodes.new('ShaderNodeAttribute');at.name='Repair field';at.attribute_name='repair_front'
            node.inputs['Emission Color'].default_value=(.025,.85,.16,1);tree.links.new(at.outputs['Fac'],node.inputs['Emission Strength'])
for i,row in enumerate(info['shoots']):
    src=sources[i%len(sources)];ob=src.copy();ob.data=src.data.copy();ob.animation_data_clear();ob.location=(0,0,0);ob.rotation_euler=(0,0,0);ob.scale=(1,1,1);bpy.context.collection.objects.link(ob)
    local=np.array([list(v.co) for v in ob.data.vertices]);height=local[:,2].max();u=np.clip(local[:,2]/height,0,1);scale=row['length']/height
    shoots.append((ob,local,u,scale,np.array(row['chain']),i))
    if K=='healing':
        ob.data.attributes.new('repair_front','FLOAT','POINT')
        for mat in ob.data.materials:
            if not mat or not mat.use_nodes:continue
            attach_repair(mat.node_tree)
stem=material('Fibrous living stem',(.033,.055,.014),.7);n=stem.node_tree.nodes;l=stem.node_tree.links;no=n.new('ShaderNodeTexNoise');no.inputs['Scale'].default_value=160;b=n.new('ShaderNodeBump');b.inputs['Distance'].default_value=.0005;l.new(no.outputs['Fac'],b.inputs['Height']);l.new(b.outputs[0],n.get('Principled BSDF').inputs['Normal'])
objects=[]
for f in frames():
    t=(f+1)/30;x=P[f]
    for o in objects:remove(o)
    objects=[];paths=[];rr=[]
    for ch in info['chains']:
        ch=np.array(ch);active=ch[birth[ch]<=t]
        if len(active)>1:paths.append(x[active]);rr.append(radii[active])
    objects.append(curve('Solved branching stems',paths,rr,stem))
    for ob,local,u,scale,ch,i in shoots:
        age=t-birth[ch[0]];ob.hide_render=age<.08
        if ob.hide_render:continue
        progress=np.clip(age/.4,0,1);along=u*(len(ch)-1);j=np.minimum(along.astype(int),len(ch)-2);a=along-j
        center=x[ch[j]]*(1-a[:,None])+x[ch[j+1]]*a[:,None];tangent=x[ch[j+1]]-x[ch[j]];tangent/=np.maximum(np.linalg.norm(tangent,axis=1)[:,None],1e-6)
        side=np.cross(tangent,np.tile([0,1,0],(len(u),1)));side/=np.maximum(np.linalg.norm(side,axis=1)[:,None],1e-6);depth=np.cross(tangent,side)
        unfurl=np.clip((progress-u)*5+.25,0,1);unfurl=unfurl*unfurl*(3-2*unfurl)
        v=center+side*(local[:,0]*scale*unfurl)[:,None]+depth*(local[:,1]*scale*unfurl)[:,None]
        if K=='healing':
            # Broken sections close locally as the repair front reaches them.
            wound=np.exp(-((u-.58)/.10)**2);repair=np.clip((age-.35)/.65,0,1);v+=side*(wound*.085*(1-repair)*np.sign(local[:,0]))[:,None]
            front=wound*np.exp(-((age-.63)/.30)**2)*4;ob.data.attributes['repair_front'].data.foreach_set('value',front.astype('f4'))
        ob.data.vertices.foreach_set('co',v.astype('f4').ravel());ob.data.update()
    finish(s,K,f)
