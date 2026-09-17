from pathlib import Path
import subprocess,sys
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;O=R.parent.parent/'outputs/cybrdelic-type/elements/motion/subelements';kinds=sys.argv[1:];canvas=Image.new('RGB',(1536,288*len(kinds)));d=ImageDraw.Draw(canvas)
for row,kind in enumerate(kinds):
 for col,t in enumerate([.67,1.4,2.67]):
  f=R/'subelements'/f'qa-{kind}-{col}.jpg';subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(t),'-i',str(O/f'{kind}.mp4'),'-frames:v','1','-vf','scale=512:-1',str(f)],check=True);canvas.paste(Image.open(f),(col*512,row*288));d.text((col*512+10,row*288+10),f'{kind} {t}s',fill='white')
out=R/'subelements'/('review-'+'-'.join(kinds)+'.jpg');canvas.save(out);print(out)
