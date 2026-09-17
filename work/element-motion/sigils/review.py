from pathlib import Path
import sys,subprocess,json,hashlib
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;out=R/'review';out.mkdir(exist_ok=True)
for key in sys.argv[1:]:
    movie=R/'media'/f'{key}.mp4';frames=[30,90,165,240,300,335,370,420];sheet=Image.new('RGB',(1280,760));d=ImageDraw.Draw(sheet)
    for i,f in enumerate(frames):
        p=out/f'{key}-{f}.jpg';subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-ss',str(f/30),'-i',str(movie),'-frames:v','1','-vf','scale=320:180','-threads','1',str(p)],check=True)
        # Four columns across two rows; keep the sequence bounded for inspection.
        x=i%4*320;y=i//4*200;sheet.paste(Image.open(p),(x,y+20));d.text((x+4,y+3),f'{key} / {f/30:.2f}s',fill='white')
    sheet=sheet.crop((0,0,1280,400));sheet.save(out/f'{key}.jpg',quality=94)
    (out/f'{key}.json').write_text(json.dumps({'frames':frames,'videoSha256':hashlib.sha256(movie.read_bytes()).hexdigest()},indent=2),encoding='utf-8')
    print(out/f'{key}.jpg')
