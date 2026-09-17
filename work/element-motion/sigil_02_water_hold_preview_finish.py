from pathlib import Path
from PIL import Image,ImageDraw
import subprocess,json,numpy as np
r=Path(__file__).resolve().parent/'sigil-02-water-hold';fs=sorted((r/'preview-frames').glob('*.jpg'));assert len(fs)==36;lines=[]
for p in fs:lines.extend(["file '"+p.as_posix()+"'",'duration 0.1'])
lines.append("file '"+fs[-1].as_posix()+"'");(r/'preview-list.txt').write_text('\n'.join(lines))
subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(r/'preview-list.txt'),'-r','30','-c:v','libx264','-threads','2','-crf','18','-pix_fmt','yuv420p',str(r/'hold-preview.mp4')],check=True)
sheet=Image.new('RGB',(1440,580));d=ImageDraw.Draw(sheet)
for k,f in enumerate([60,81,102,123,144,165]):
 x=k%3*480;y=k//3*290;sheet.paste(Image.open(r/'preview-frames'/f'{f:04}.jpg').resize((480,270)),(x,y+20));d.text((x+8,y+3),str(round(f/30,1))+'s',fill=(180,180,180))
sheet.save(r/'hold-motion-review.jpg',quality=94);print('36-frame hold preview and reduced motion sheet saved')
