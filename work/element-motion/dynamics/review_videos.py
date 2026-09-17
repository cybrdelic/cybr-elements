"""Decode complete candidate clips into bounded contact sheets on disk."""
from pathlib import Path
import subprocess,sys,json
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;O=R/'sequence-review';O.mkdir(exist_ok=True)
for k in sys.argv[1:]:
    movie=R/'media'/f'{k}.mp4';receipt=json.loads((R/'media'/f'{k}.json').read_text(encoding='utf-8'))
    frames=[10,24,39,51,64,78,96,118] if 'lightning' not in k else [5,12,20,26,33,40,51,90]
    canvas=Image.new('RGB',(1280,400));draw=ImageDraw.Draw(canvas)
    for i,f in enumerate(frames):
        p=O/f'{k}-{f:04}.jpg'
        subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-ss',str(f/30),'-i',str(movie),'-frames:v','1','-vf','scale=320:180','-threads','1',str(p)],check=True)
        x=(i%4)*320;y=(i//4)*200;canvas.paste(Image.open(p),(x,y+20));draw.text((x+6,y+4),f'{k} {f/30:.2f}s',fill='white')
    canvas.save(O/f'{k}.jpg',quality=94)
    (O/f'{k}.json').write_text(json.dumps({'id':k,'frames':frames,'videoSha256':receipt['sha256'],'size':[1280,400]},indent=2),encoding='utf-8')
    print(O/f'{k}.jpg')
