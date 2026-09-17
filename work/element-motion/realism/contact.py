from pathlib import Path
import sys,math
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;items=[q.split(':') for q in sys.argv[2:]];cols=3 if len(items)>4 else 2;width=512 if cols==3 else 640;height=width*9//16;sh=Image.new('RGB',(width*cols,(height+24)*math.ceil(len(items)/cols)));d=ImageDraw.Draw(sh)
for i,item in enumerate(items):
 k=item[0];f=int(item[1]) if len(item)>1 else 42;p=R/f'{k}-frames/{f:04}.jpg'
 if not p.exists():p=p.with_suffix('.png')
 if p.exists():sh.paste(Image.open(p).convert('RGB').resize((width,height)),(i%cols*width,i//cols*(height+24)+24))
 d.text((i%cols*width+8,i//cols*(height+24)+5),f'{k} {f/30:.2f}s',fill='white')
sh.save(R/sys.argv[1],quality=93);print(str(R/sys.argv[1]))
