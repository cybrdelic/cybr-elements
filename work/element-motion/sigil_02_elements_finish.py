"""Encode, decode-audit, and publish only visually reviewed 02 media."""
from pathlib import Path
import json,subprocess,hashlib,shutil,sys
import cv2,numpy as np
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;O=R/'sigil-02-elements';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
sources={'air':O/'air-02-v2.mp4','water':O/'water-02.mp4','earth':O/'earth-02.mp4','lightning':O/'lightning-02-v4.mp4'}
totals={'water':270,'earth':294,'air':294,'lightning':294}
def encode(element):
 folder=O/('earth-frames-v3' if element=='earth' else 'water-frames')
 files=sorted(folder.glob('*.jpg'));assert len(files)==294,(element,len(files));assert [p.name for p in files]==[f'{i:04}.jpg' for i in range(294)]
 subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-i',str(folder/'%04d.jpg'),'-frames:v',str(totals[element]),'-c:v','libx264','-threads','2','-preset','slow','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(sources[element])],check=True)
def audit(element):
 path=sources[element];meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,avg_frame_rate:format=duration','-of','json',str(path)],text=True));s=meta['streams'][0]
 assert (s['width'],s['height'],int(s['nb_frames']),s['avg_frame_rate'])==(1920,1080,totals[element],'30/1')
 cap=cv2.VideoCapture(str(path));chosen=[30,75,135,180,220,min(270,totals[element]-1)] if element!='lightning' else [41,71,126,160,195,270];sheet=Image.new('RGB',(1280,1140));draw=ImageDraw.Draw(sheet);count=0;rows=[]
 while True:
  ok,bgr=cap.read()
  if not ok:break
  rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);small=cv2.resize(rgb,(640,360),interpolation=cv2.INTER_AREA);lum=small@np.array([.2126,.7152,.0722]);corners=np.concatenate([small[:10,:10].ravel(),small[:10,-10:].ravel(),small[-10:,:10].ravel(),small[-10:,-10:].ravel()])
  rows.append({'frame':count,'meanLuma':float(lum.mean()),'cornerMax':int(corners.max())})
  if count in chosen:
   i=chosen.index(count);x=i%2*640;y=i//2*380;sheet.paste(Image.fromarray(small),(x,y+20));draw.text((x+12,y+4),f'{element.upper()} / {count/30:.2f}s',fill=(180,180,180))
  if count==(160 if element=='lightning' else 165):Image.fromarray(rgb).resize((1280,720)).save(O/f'{element}-poster.jpg',quality=95)
  count+=1
 cap.release();assert count==totals[element]
 sheet.save(O/f'{element}-review.jpg',quality=93)
 report={'element':element,'decodedFrames':count,'metadata':meta,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'maxCorner':max(r['cornerMax'] for r in rows),'peakLuma':max(r['meanLuma'] for r in rows),'endLuma':rows[-1]['meanLuma'],'visualStatus':'pending','rows':rows}
 (O/f'{element}-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['metadata','rows']}))
def publish():
 assert hashlib.sha256((P/'fire-02.mp4').read_bytes()).hexdigest()=='3bb0dd50aa6c2f4ce55edbf18753fc9db27b656d83d4efbcd29a4a33282e83f6'
 for e,path in sources.items():
  a=json.loads((O/f'{e}-audit.json').read_text());assert a['visualStatus']=='reviewed',e;assert hashlib.sha256(path.read_bytes()).hexdigest()==a['sha256']
  shutil.copy2(path,P/f'{e}-02.mp4');shutil.copy2(O/f'{e}-poster.jpg',P/f'{e}-poster.jpg')
 if not (O/'approved-fire-page.html').exists():shutil.copy2(P/'index.html',O/'approved-fire-page.html')
 shutil.copy2(O/'gallery.html',P/'index.html')
 gallery=P.parents[1]/'index.html';page=gallery.read_text(encoding='utf-8');gallery.write_text(page.replace('02 fire sigil ↗','02 elemental sigils ↗'),encoding='utf-8')
 print('Published four additional 02 elements; approved fire byte-identical.')
mode=sys.argv[1]
if mode=='encode':encode(sys.argv[2]);audit(sys.argv[2])
elif mode=='audit':audit(sys.argv[2])
elif mode=='publish':publish()
