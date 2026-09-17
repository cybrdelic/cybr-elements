from pathlib import Path
p=Path('work/render_script_fire.py').read_text().replace('from font_motion import','from sans_motion import').replace('script-fire','sans-fire')
Path('work/render_sans_fire.py').write_text(p)
from PIL import Image,ImageDraw
import sans_motion as m
im=Image.new('RGB',(1500,420),'#111111');d=ImageDraw.Draw(im)
for p in m.curves:d.line([(750+x*145,370-z*130) for x,z in p],fill='#f9b658',width=5)
im.save('work/sans-proof.jpg',quality=93)
print({'duration':m.WRITE,'strokes':len(m.curves)})
