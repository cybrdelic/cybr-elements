from pathlib import Path
R=Path(__file__).resolve().parent;s=(R/'plants.py').read_text(encoding='utf-8')
s=s.replace("out=R/'plants-frames'", "out=R/'healing-frames'").replace("R/'plants-report.json'", "R/'healing-report.json'")
s=s.replace('front=np.clip((t-.08)/1.6,0,1)','front=1.0')
s=s.replace('g=float(np.clip(age/.9,0,1));ob.hide_render=g<.005','repair=float(np.clip(age/.7,0,1));g=1.0;ob.hide_render=False')
s=s.replace("ob.data.vertices.foreach_set('co',vv.ravel());ob.data.update()", """
  # Torn leaf sides are displaced until the moving repair reaches this shoot.
  tear=np.sin(v[:,2]*170+v[:,0]*65);damage=np.clip((np.abs(v[:,0])-.006)*70,0,1)
  vv+=((1-repair)*damage*np.sign(tear)*.022)[:,None]*side
  ob.data.vertices.foreach_set('co',vv.ravel());ob.data.update()
  at=ob.data.attributes.get('Repair') or ob.data.attributes.new('Repair','FLOAT','POINT');at.data.foreach_set('value',np.full(len(v),repair))
  glow=ob.data.attributes.get('RepairFront') or ob.data.attributes.new('RepairFront','FLOAT','POINT');glow.data.foreach_set('value',np.full(len(v),max(0,1-abs(age-.25)/.35)*.35))""")
marker="objects=[];frames="
extra="""
# Keep the photographic leaf detail while dry tissue regains pigment.
for ob,*_ in shoots:
 for i,mat in enumerate(list(ob.data.materials)):
  if mat is None:continue
  mat=mat.copy();ob.data.materials[i]=mat;n=mat.node_tree.nodes;l=mat.node_tree.links;p=n.get('Principled BSDF')
  if not p:continue
  old=p.inputs['Base Color'].links[0].from_socket if p.inputs['Base Color'].is_linked else None
  mix=n.new('ShaderNodeMixRGB');mix.inputs[1].default_value=(.085,.028,.006,1)
  if old:l.new(old,mix.inputs[2])
  else:mix.inputs[2].default_value=(.055,.15,.02,1)
  attr=n.new('ShaderNodeAttribute');attr.attribute_name='Repair';l.new(attr.outputs['Fac'],mix.inputs[0]);l.new(mix.outputs[0],p.inputs['Base Color'])
  front=n.new('ShaderNodeAttribute');front.attribute_name='RepairFront';p.inputs['Emission Color'].default_value=(.10,.36,.035,1);l.new(front.outputs['Fac'],p.inputs['Emission Strength'])
"""
s=s.replace(marker,extra+'\n'+marker)
(R/'healing.py').write_text(s,encoding='utf-8');print('Healing uses the source foliage and a travelling repair front')
