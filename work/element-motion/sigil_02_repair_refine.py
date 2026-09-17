from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'sigil_02_repair_earth.py').read_text()
s=s.replace('from mathutils import Vector','from mathutils import Vector,noise as rocknoise')
s=s.replace("return m\n", """# Large mineral patches survive the camera distance; fine noise alone did not.
 tex=m.node_tree.nodes.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=5.3;tex.inputs['Detail'].default_value=5;tex.inputs['Roughness'].default_value=.72
 mineral=m.node_tree.nodes.new('ShaderNodeValToRGB');mineral.color_ramp.elements[0].position=.24;mineral.color_ramp.elements[0].color=(*[c*.18 for c in color],1);mineral.color_ramp.elements[1].position=.73;mineral.color_ramp.elements[1].color=(*[c*1.3 for c in color],1)
 m.node_tree.links.new(tex.outputs['Fac'],mineral.inputs[0]);m.node_tree.links.new(mineral.outputs[0],n.inputs['Base Color']);n.inputs['Specular IOR Level'].default_value=.24
 return m
""")
needle='  layerMeshes[family]=lm'
replacement='''  # Physical surface relief on the shared high-resolution source meshes.
  # This changes silhouette and self-shadowing, not just a normal texture.
  lm.update()
  originals=[(v.co.copy(),v.normal.copy()) for v in lm.vertices]
  for v,(co,no) in zip(lm.vertices,originals):
   shift=Vector((family*.137,family*.071,family*.093))
   ridge=rocknoise.noise_vector(co*8.7+shift).x
   grain=rocknoise.noise_vector(co*39.1-shift).y
   v.co=co+no*(ridge*.033+grain*.010)
  lm.update()
  layerMeshes[family]=lm'''
assert needle in s;s=s.replace(needle,replacement)
s=s.replace("'sigil-02-repair/earth-pilot'","'sigil-02-repair/earth-pilot-detail'")
(R/'sigil_02_repair_earth_detail.py').write_text(s)
s=(R/'sigil_02_repair_lightning.py').read_text()
s=s.replace("dest=B/f'discharge-{event:02}.npz'","dest=B/f'discharge-branched-{event:02}.npz'")
s=s.replace('lengths[-1]/.28','lengths[-1]/.85').replace("(.065+widths[nearest]*.75)","(.25+widths[nearest]*.75)").replace('corridor[ids]**1.8','corridor[ids]**.65').replace('+.12/np.maximum(ds,.10)','+.70/np.maximum(ds,.10)')
s=s.replace('length[j]>.24','length[j]>.14').replace('length[child]>.22','length[child]>.13')
s=s.replace("radius=(.29 if net['trunk'][j] else .12)","radius=(.42 if net['trunk'][j] else .12)").replace('interpolation=cv2.INTER_AREA)*145','interpolation=cv2.INTER_AREA)*230')
s=s.replace("B/'lightning-pilot.jpg'","B/'lightning-pilot-branched.jpg'")
(R/'sigil_02_repair_lightning_branched.py').write_text(s)
print('Prepared stone relief and branching refinements.')
