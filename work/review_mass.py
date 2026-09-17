from pathlib import Path
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent
frames=[6,18,30,48,60,78,90,102,114,132,156,180]
sheet=Image.new('RGB',(1600,810),'#101012');d=ImageDraw.Draw(sheet)
for i,k in enumerate(frames):
    x=i%4*400;y=i//4*270
    im=Image.open(root/'mass-frames'/f'{k:04d}.jpg').resize((400,225))
    sheet.paste(im,(x,y));d.text((x+8,y+240),f'{k/30:.1f}s',fill='white')
sheet.save(root/'mass-contact.jpg',quality=92)
print(root/'mass-contact.jpg')
