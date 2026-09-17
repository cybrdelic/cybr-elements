"""Encode, decode every frame, preserve predecessors, and publish reviewed revisions."""
from pathlib import Path
import json,subprocess,hashlib,shutil,sys
import cv2,numpy as np
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;O=R/'sigil-02-alive';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
FOLDERS={'earth':O/'earth-frames'}
def audit(element):
 movie=O/f'{element}-candidate.mp4';meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,avg_frame_rate:format=duration','-of','json',str(movie)],text=True));m=meta['streams'][0]
 assert (m['width'],m['height'],int(m['nb_frames']),m['avg_frame_rate'])==(1920,1080,300,'30/1')
 cap=cv2.VideoCapture(str(movie));picks=[30,75,165,192,219,299];sheet=Image.new('RGB',(1280,1140));draw=ImageDraw.Draw(sheet);rows=[];previous=None;f=0
 while True:
  ok,bgr=cap.read()
  if not ok:break
  rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);small=cv2.resize(rgb,(640,360),interpolation=cv2.INTER_AREA);lum=small@np.array([.2126,.7152,.0722]);corners=np.concatenate([small[:8,:8].ravel(),small[:8,-8:].ravel(),small[-8:,:8].ravel(),small[-8:,-8:].ravel()])
  rows.append(dict(frame=f,meanLuma=float(lum.mean()),cornerMax=int(corners.max()),frameDifference=float(np.abs(small.astype(float)-previous).mean()) if previous is not None else 0));previous=small.astype(float)
  if f in picks:
   i=picks.index(f);x=i%2*640;y=i//2*380;sheet.paste(Image.fromarray(small),(x,y+20));draw.text((x+12,y+4),f'{element.upper()} / {f/30:.2f}s',fill=(190,190,190));Image.fromarray(rgb).resize((1280,720)).save(O/f'{element}-decoded-{f:04}.jpg',quality=94)
  if f==90:Image.fromarray(rgb).resize((1280,720)).save(O/f'{element}-poster.jpg',quality=95)
  f+=1
 cap.release();assert f==300;sheet.save(O/f'{element}-review.jpg',quality=94)
 report=dict(element=element,frames=f,metadata=meta,sha256=hashlib.sha256(movie.read_bytes()).hexdigest(),visualStatus='pending',endLuma=rows[-1]['meanLuma'],maxCorner=max(r['cornerMax'] for r in rows),holdMeanFrameDifference=float(np.mean([r['frameDifference'] for r in rows[75:174]])),rows=rows)
 (O/f'{element}-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['metadata','rows']}))
def encode(element):
 if element in FOLDERS:
  folder=FOLDERS[element];assert [p.name for p in sorted(folder.glob('*.jpg'))]==[f'{f:04}.jpg' for f in range(300)]
  subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-i',str(folder/'%04d.jpg'),'-c:v','libx264','-threads','2','-preset','slow','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(O/f'{element}-candidate.mp4')],check=True)
 audit(element)

if __name__=='__main__':
 if sys.argv[1]=='encode':encode(sys.argv[2])
 elif sys.argv[1]=='audit':audit(sys.argv[2])
