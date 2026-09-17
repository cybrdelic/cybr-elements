from pathlib import Path
import cv2, json, numpy as np
from PIL import Image, ImageDraw

B=Path(__file__).resolve().parent
P=B.parents[2]/'outputs/cybrdelic-type/elements/motion/bending'

def frame(path, n):
    c=cv2.VideoCapture(str(path)); c.set(cv2.CAP_PROP_POS_FRAMES,n)
    ok,a=c.read();c.release()
    if not ok: raise RuntimeError(f'Missing {path} frame {n}')
    return Image.fromarray(cv2.cvtColor(a,cv2.COLOR_BGR2RGB))

def sheet(cells, path, columns=2, width=720):
    height=round(width*9/16)+26
    out=Image.new('RGB',(width*columns,height*((len(cells)+columns-1)//columns)))
    d=ImageDraw.Draw(out)
    for i,(title,im) in enumerate(cells):
        x=i%columns*width;y=i//columns*height
        out.paste(im.resize((width,height-26),Image.Resampling.LANCZOS),(x,y+26));d.text((x+12,y+8),title,fill='#bbbbbb')
    out.save(path,quality=92)
    print(str(path),out.size)

if __name__=='__main__':
    cells=[]
    for n in [42,60,75,90,105,119]:
        p=B/'water-smooth-frames'/f'{n:04d}.jpg'
        if p.exists():cells.append((f'WATER {n/30:.2f}s',Image.open(p).convert('RGB')))
    sheet(cells,B/'water-late-review.jpg',columns=2,width=480)
    cells=[]
    for n in [21,41,50]:
        cells.extend([(f'PREVIOUS LIGHTNING {n/30:.2f}s',frame(P/'lightning.mp4',n)),(f'REBUILT LIGHTNING {n/30:.2f}s',frame(B/'lightning-v2.mp4',n))])
    sheet(cells,B/'lightning-comparison.jpg',columns=2,width=480)
    cells=[]
    for n in [21,42,60]:
        p=B/'water-smooth-frames'/f'{n:04d}.jpg'
        cells.extend([(f'PREVIOUS WATER {n/30:.2f}s',frame(P/'water.mp4',n)),(f'REBUILT WATER {n/30:.2f}s',Image.open(p).convert('RGB'))])
    sheet(cells,B/'water-comparison.jpg',columns=2,width=480)
    cells=[(f'{n/30:.3f}s',frame(B/'lightning-v2.mp4',n)) for n in range(35,47)]
    sheet(cells,B/'lightning-timing.jpg',columns=3,width=400)
    m=json.loads((B/'water-particles/manifest.json').read_text())
    print(json.dumps({'waterFrames':len(m['frames']),'complete':m['complete'],'allFinite':all(x['finite'] for x in m['frames']),
      'pressureFailures':m['frames'][-1]['pressureFailures'],'particles':m['frames'][-1]['particles'],
      'renderedFrames':len(list((B/'water-smooth-frames').glob('*.jpg')))},indent=2))
