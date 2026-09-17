from pathlib import Path
R=Path(__file__).resolve().parent
p=R/'entities.py';s=p.read_text(encoding='utf-8')
s=s.replace("p=n.get('Principled BSDF')\n   if not p:continue", "p=next((node for node in n if node.type=='BSDF_PRINCIPLED'),None)\n   if not p:continue\n   original=p.inputs['Base Color'].links[0].from_socket if p.inputs['Base Color'].is_linked else None\n   dark=n.new('ShaderNodeMixRGB');dark.blend_type='MULTIPLY';dark.inputs[0].default_value=1;dark.inputs[2].default_value=(.018,.022,.03,1)\n   if original:l.new(original,dark.inputs[1])\n   else:dark.inputs[1].default_value=(.5,.5,.5,1)\n   l.new(dark.outputs[0],p.inputs['Base Color']);p.inputs['Roughness'].default_value=.3")
s=s.replace("l.new(vor.outputs['Distance'],edge.inputs[0]);charge=", "l.new(vor.outputs['Distance'],edge.inputs[0]);charge=")
s=s.replace("nt.links.new(ra.outputs[0],p.inputs['Emission Strength'])", "nt.links.new(ra.outputs[0],p.inputs['Emission Strength']);tr=nt.nodes.new('ShaderNodeBsdfTransparent');mix=nt.nodes.new('ShaderNodeMixShader');mix.inputs[0].default_value=.25;nt.links.new(tr.outputs[0],mix.inputs[1]);nt.links.new(p.outputs[0],mix.inputs[2]);nt.links.new(mix.outputs[0],nt.nodes.get('Material Output').inputs[0])")
p.write_text(s,encoding='utf-8')
prefix=s[:s.index("if K in ['spirit-projection','energy']:")]
tail='''body,v=sculpture();body.location=(.0,0,1.6);body.rotation_euler.z=-.14
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
'''
(R/'spirit.py').write_text(prefix+tail,encoding='utf-8')
print('Entity materials retain surface detail with controlled field contrast')
