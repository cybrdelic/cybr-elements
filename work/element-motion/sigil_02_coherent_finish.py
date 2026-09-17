"""Encode, decode every frame, preserve predecessors, and publish reviewed revisions."""
from pathlib import Path
import json,subprocess,hashlib,shutil,sys
import cv2,numpy as np
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;O=R/'sigil-02-coherent';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
FOLDERS={'water':R/'sigil-02-water-hold/frames','earth':O/'earth-frames'}
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
def publish():
 expected={'fire':'3bb0dd50aa6c2f4ce55edbf18753fc9db27b656d83d4efbcd29a4a33282e83f6','air':'80d89a5bd8ccb347da1659b5dcc8f8417db156bffe66759498adab4cb40b7120'}
 for e,digest in expected.items():assert hashlib.sha256((P/f'{e}-02.mp4').read_bytes()).hexdigest()==digest
 artifacts=[]
 for e in ['water','earth','lightning']:
  a=json.loads((O/f'{e}-audit.json').read_text());assert a['visualStatus']=='agent-reviewed-improvement',e;src=O/f'{e}-candidate.mp4';assert hashlib.sha256(src.read_bytes()).hexdigest()==a['sha256']
  shutil.copy2(src,P/f'{e}-02-r3.mp4');shutil.copy2(O/f'{e}-poster.jpg',P/f'{e}-r3-poster.jpg');artifacts.append(dict(element=e,path=str(P/f'{e}-02-r3.mp4'),sha256=a['sha256'],duration=10))
 page=(P/'index.html').read_text(encoding='utf-8');backup=O/'previous-player.html'
 if not backup.exists():backup.write_text(page,encoding='utf-8')
 page=page.replace("revised.has(name)?`${name}-r2-poster.jpg`", "revised.has(name)?`${name}-r3-poster.jpg`")
 page=page.replace("revised.has(name)?`${name}-02-r2.mp4`", "revised.has(name)?`${name}-02-r3.mp4`")
 page=page.replace("showPrevious?`${active}-poster.jpg`:`${active}-r2-poster.jpg`", "showPrevious?`${active}-r2-poster.jpg`:`${active}-r3-poster.jpg`")
 page=page.replace("showPrevious?`${active}-02.mp4`:`${active}-02-r2.mp4`", "showPrevious?`${active}-02-r2.mp4`:`${active}-02-r3.mp4`")
 assert '02-r3.mp4' in page and page.count('id="previous"')==1
 (P/'index.html').write_text(page,encoding='utf-8')
 (O/'publication.json').write_text(json.dumps(dict(artifacts=artifacts,preserved=expected,allPreviousMediaRetained=True,userAccepted=False),indent=2));print('Published three reviewed revisions; fire, air and all prior media retained.')
if __name__=='__main__':
 mode=sys.argv[1]
 if mode=='encode':encode(sys.argv[2])
 elif mode=='audit':audit(sys.argv[2])
 elif mode=='publish':publish()
