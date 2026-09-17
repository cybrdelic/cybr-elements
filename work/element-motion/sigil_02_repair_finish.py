"""Encode and inspect candidates; publishing is a separate, explicit local step."""
from pathlib import Path
import json,subprocess,hashlib,shutil,sys
import cv2,numpy as np
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;O=R/'sigil-02-repair';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
TOTAL={'water':240,'earth':192,'lightning':168}
PATHS={e:O/f'{e}-candidate.mp4' for e in TOTAL}
def encode(e):
 if e!='lightning':
  folder=O/('water-final-frames' if e=='water' else f'{e}-frames');files=sorted(folder.glob('*.jpg'));assert [p.name for p in files]==[f'{f:04}.jpg' for f in range(TOTAL[e])],(e,len(files))
  subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-i',str(folder/'%04d.jpg'),'-c:v','libx264','-threads','2','-preset','slow','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(PATHS[e])],check=True)
 audit(e)
def audit(e):
 meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,avg_frame_rate:format=duration','-of','json',str(PATHS[e])],text=True));s=meta['streams'][0];assert (s['width'],s['height'],int(s['nb_frames']),s['avg_frame_rate'])==(1920,1080,TOTAL[e],'30/1')
 picks=[24,45,66,87,117,160] if e!='lightning' else [12,49,61,83,124,155];sheet=Image.new('RGB',(1280,1140));draw=ImageDraw.Draw(sheet)
 cap=cv2.VideoCapture(str(PATHS[e]));rows=[];previous=None;f=0
 while True:
  ok,im=cap.read()
  if not ok:break
  rgb=cv2.cvtColor(im,cv2.COLOR_BGR2RGB);small=cv2.resize(rgb,(640,360),interpolation=cv2.INTER_AREA);lum=small@np.array([.2126,.7152,.0722]);corners=np.concatenate([small[:8,:8].ravel(),small[:8,-8:].ravel(),small[-8:,:8].ravel(),small[-8:,-8:].ravel()])
  rows.append(dict(frame=f,meanLuma=float(lum.mean()),cornerMax=int(corners.max()),frameDifference=float(np.abs(small.astype(float)-previous).mean()) if previous is not None else 0.))
  previous=small.astype(float)
  if f in picks:
   k=picks.index(f);x=k%2*640;y=k//2*380;sheet.paste(Image.fromarray(small),(x,y+20));draw.text((x+12,y+4),f'{e.upper()} / {f/30:.2f}s',fill=(180,180,180))
  if f==(61 if e=='lightning' else 60):Image.fromarray(rgb).resize((1280,720)).save(O/f'{e}-poster.jpg',quality=95)
  if f in [45,61,66,87,117,155,160,TOTAL[e]-1]:Image.fromarray(rgb).resize((1280,720)).save(O/f'{e}-decoded-{f:04}.jpg',quality=94)
  f+=1
 cap.release();assert f==TOTAL[e];sheet.save(O/f'{e}-review.jpg',quality=94)
 report=dict(element=e,frames=f,metadata=meta,sha256=hashlib.sha256(PATHS[e].read_bytes()).hexdigest(),visualStatus='pending',endLuma=rows[-1]['meanLuma'],maxCorner=max(r['cornerMax'] for r in rows),rows=rows)
 (O/f'{e}-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['rows','metadata']}))
def publish():
 preserved={e:hashlib.sha256((P/f'{e}-02.mp4').read_bytes()).hexdigest() for e in ['fire','air']}
 assert preserved['fire']=='3bb0dd50aa6c2f4ce55edbf18753fc9db27b656d83d4efbcd29a4a33282e83f6';assert preserved['air']=='80d89a5bd8ccb347da1659b5dcc8f8417db156bffe66759498adab4cb40b7120'
 for e in TOTAL:
  a=json.loads((O/f'{e}-audit.json').read_text());assert a['visualStatus']=='reviewed-improvement',e;assert hashlib.sha256(PATHS[e].read_bytes()).hexdigest()==a['sha256']
  shutil.copy2(PATHS[e],P/f'{e}-02-r2.mp4');shutil.copy2(O/f'{e}-poster.jpg',P/f'{e}-r2-poster.jpg')
 page=(P/'index.html').read_text(encoding='utf-8');(O/'previous-player.html').write_text(page,encoding='utf-8')
 page=page.replace('id="reference"','id="reference"',1)
 page=page.replace('<span class="meta">','<button id="previous" aria-pressed="false" hidden>Previous version</button><span class="meta">',1)
 page=page.replace("function select(name,push=true)","const revised=new Set(['water','earth','lightning']),previous=document.getElementById('previous');let active='fire',showPrevious=false;\nfunction select(name,push=true)")
 page=page.replace("film.pause();film.poster=name==='fire'?'poster.jpg':`${name}-poster.jpg`;film.src=`${name}-02.mp4`;", "film.pause();active=name;showPrevious=false;previous.hidden=!revised.has(name);previous.setAttribute('aria-pressed','false');previous.textContent='Previous version';film.poster=name==='fire'?'poster.jpg':revised.has(name)?`${name}-r2-poster.jpg`:`${name}-poster.jpg`;film.src=revised.has(name)?`${name}-02-r2.mp4`:`${name}-02.mp4`;")
 page=page.replace("film.addEventListener('loadedmetadata'", "previous.addEventListener('click',()=>{showPrevious=!showPrevious;film.pause();art.hidden=true;reference.setAttribute('aria-expanded','false');reference.textContent='Compare 02 artwork';film.poster=showPrevious?`${active}-poster.jpg`:`${active}-r2-poster.jpg`;film.src=showPrevious?`${active}-02.mp4`:`${active}-02-r2.mp4`;download.href=film.src;download.download=`cybrdelic-02-${active}${showPrevious?'-previous':'-revised'}.mp4`;previous.setAttribute('aria-pressed',String(showPrevious));previous.textContent=showPrevious?'Return to revision':'Previous version';film.load();film.play().catch(()=>{});});\nfilm.addEventListener('loadedmetadata'")
 assert '02-r2.mp4' in page and page.count('id="previous"')==1
 (P/'index.html').write_text(page,encoding='utf-8')
 for e,digest in preserved.items():assert hashlib.sha256((P/f'{e}-02.mp4').read_bytes()).hexdigest()==digest
 (O/'publication.json').write_text(json.dumps(dict(status='revised-candidates-published',preserved=preserved,oldMediaRetained=True,visualAcceptance='User review still determines acceptance; revisions are not labeled photoreal or final.'),indent=2));print('Published revisions; prior media and approved fire/air preserved.')
if __name__=='__main__':
 mode=sys.argv[1]
 if mode=='encode':encode(sys.argv[2])
 elif mode=='audit':audit(sys.argv[2])
 elif mode=='publish':publish()
