from pathlib import Path
import sys
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent
items=sys.argv[1:];canvas=Image.new('RGB',(1280,380*((len(items)+1)//2)),(9,9,9));d=ImageDraw.Draw(canvas)
for i,item in enumerate(items):
    name,f=item.split(':');im=Image.open(R/'frames'/name/f'{int(f):04}.jpg');im.thumbnail((640,360));x=(i%2)*640;y=(i//2)*380;canvas.paste(im,(x,y+20));d.text((x+10,y+4),f'{name}  {int(f)/30:.2f}s',fill='white')
canvas.thumbnail((1600,1600));p=R/'review.jpg';canvas.save(p,quality=90);print(str(p.resolve()))
