from pathlib import Path
R=Path(__file__).resolve().parent;p=R/'fracture.py';s=p.read_text(encoding='utf-8')
needle="sub.levels=2;sub.render_levels=2"
replace="""sub.levels=2;sub.render_levels=2
   if K=='ice':
    texture=bpy.data.textures.get('Frozen surface relief') or bpy.data.textures.new('Frozen surface relief','CLOUDS');texture.noise_scale=.075;texture.noise_depth=2;disp=shell.modifiers.new('Uneven frozen surface','DISPLACE');disp.texture=texture;disp.texture_coords='GLOBAL';disp.strength=.09;disp.mid_level=.5
    fine=bpy.data.textures.get('Small frost relief') or bpy.data.textures.new('Small frost relief','CLOUDS');fine.noise_scale=.018;fine.noise_depth=1;micro=shell.modifiers.new('Small frost pits','DISPLACE');micro.texture=fine;micro.texture_coords='GLOBAL';micro.strength=.013;micro.mid_level=.5"""
assert needle in s;s=s.replace(needle,replace);p.write_text(s,encoding='utf-8')
print('Physical surface relief added to the frozen mass')
