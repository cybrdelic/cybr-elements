from pathlib import Path
R=Path(__file__).resolve().parent;p=R/'fracture.py';s=p.read_text(encoding='utf-8');marker="air=material('Enclosed ice fissures'"
insert="""
if K=='ice':
 p.inputs['Transmission Weight'].default_value=.9;p.inputs['Subsurface Weight'].default_value=.065;p.inputs['Base Color'].default_value=(.89,.96,1,1)
 tc=n.new('ShaderNodeTexCoord');mapping=n.new('ShaderNodeVectorMath');mapping.operation='SCALE';mapping.inputs['Scale'].default_value=1.8;l.new(tc.outputs['Object'],mapping.inputs[0])
 for suffix in ['NormalGL','Roughness']:
  tx=n.new('ShaderNodeTexImage');tx.image=bpy.data.images.load(str(R/'assets/ice002'/f'Ice002_2K-JPG_{suffix}.jpg'));tx.image.colorspace_settings.name='Non-Color';tx.projection='BOX';tx.projection_blend=.3;l.new(mapping.outputs[0],tx.inputs[0])
  if suffix=='NormalGL':
   normal=n.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.9;l.new(tx.outputs[0],normal.inputs['Color']);l.new(normal.outputs[0],p.inputs['Normal'])
  else:
   remap=n.new('ShaderNodeMapRange');remap.inputs['To Min'].default_value=.035;remap.inputs['To Max'].default_value=.36;l.new(tx.outputs[0],remap.inputs[0]);l.new(remap.outputs[0],p.inputs['Roughness'])
"""
assert marker in s;s=s.replace(marker,insert+'\n'+marker,1);p.write_text(s,encoding='utf-8');print('Ice002 PBR fracture and frost scale applied')
