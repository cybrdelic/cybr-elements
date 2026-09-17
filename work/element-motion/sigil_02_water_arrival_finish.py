"""Water-only delivery, with complete decode and preserved comparison media."""
from pathlib import Path
import json,sys,subprocess,hashlib,shutil,gzip
import cv2,numpy as np
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;O=R/'sigil-02-water-arrival';F=O/'full';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def preview():
 files=[O/f'preview-frames/{f:04}.jpg' for f in range(9,121,3)];assert all(p.exists() for p in files)
 listing=O/'preview-input.txt';listing.write_text('\n'.join("file '"+p.resolve().as_posix()+"'\nduration 0.1" for p in files))
 subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(listing),'-c:v','libx264','-threads','2','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(O/'cpu-formation-preview.mp4')],check=True)
 print('CPU motion preview encoded: 38 reconstructed native states, 3.8 seconds.')
def encode():
 assert [p.name for p in sorted((F/'frames').glob('*.jpg'))]==[f'{f:04}.jpg' for f in range(300)]
 subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-i',str(F/'frames/%04d.jpg'),'-c:v','libx264','-threads','2','-preset','slow','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(F/'water-candidate.mp4')],check=True)
 audit()
def audit():
 movie=F/'water-candidate.mp4';meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,avg_frame_rate:format=duration','-of','json',str(movie)],text=True));stream=meta['streams'][0]
 assert (stream['width'],stream['height'],int(stream['nb_frames']),stream['avg_frame_rate'])==(1920,1080,300,'30/1')
 picks=[15,30,48,66,90,165,210,299];sheet=Image.new('RGB',(1280,1520));draw=ImageDraw.Draw(sheet);cap=cv2.VideoCapture(str(movie));rows=[];previous=None;f=0
 while True:
  ok,bgr=cap.read()
  if not ok:break
  rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);small=cv2.resize(rgb,(640,360),interpolation=cv2.INTER_AREA);corners=np.concatenate([small[:8,:8].ravel(),small[:8,-8:].ravel(),small[-8:,:8].ravel(),small[-8:,-8:].ravel()]);lum=small@np.array([.2126,.7152,.0722])
  rows.append(dict(frame=f,meanLuma=float(lum.mean()),cornerMax=int(corners.max()),frameDifference=float(np.abs(small.astype(float)-previous).mean()) if previous is not None else 0));previous=small.astype(float)
  if f in picks:
   i=picks.index(f);x=i%2*640;y=i//2*380;sheet.paste(Image.fromarray(small),(x,y+20));draw.text((x+10,y+4),f'WATER / {f/30:.2f}s',fill=(190,190,190));Image.fromarray(rgb).resize((1280,720)).save(F/f'decoded-{f:04}.jpg',quality=93)
  if f==105:Image.fromarray(rgb).resize((1280,720)).save(F/'poster.jpg',quality=95)
  f+=1
 cap.release();assert f==300;sheet.save(F/'review.jpg',quality=93)
 native=json.loads((F/'particles/manifest.json').read_text());assert native['complete'] and len(native['frames'])==300
 assert all(r['finite'] and r['pressure']['converged'] and not r['capacityRejected'] and abs(r['sourceVolumeBalance'])<1e-8 for r in native['frames'])
 mesh=[json.loads((F/f'mesh/{i:04}.json').read_text()) for i in range(300)]
 a=cv2.imread(str(F/'frames/0165.jpg'));b=cv2.imread(str(R/'sigil-02-water-hold/frames/0165.jpg'));am=a.max(2)>18;bm=b.max(2)>18
 report=dict(metadata=meta,sha256=digest(movie),frames=f,nativeFinite=True,pressureConverged=True,sourceVolumeBalanceMax=max(abs(r['sourceVolumeBalance']) for r in native['frames']),maxHoldUnresolvedFraction=max(r['unresolvedMarkerFraction'] for r in mesh[75:174]),oldHoldSilhouetteIoU=float((am&bm).sum()/max(1,(am|bm).sum())),endLuma=rows[-1]['meanLuma'],cornerMax=max(r['cornerMax'] for r in rows),visualStatus='pending',userAccepted=False,rows=rows)
 (F/'audit.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['metadata','rows']}))
def publish():
 a=json.loads((F/'audit.json').read_text());assert a['visualStatus']=='agent-reviewed-improvement';assert digest(F/'water-candidate.mp4')==a['sha256']
 protected=['fire-02.mp4','air-02.mp4','earth-02-r3.mp4','lightning-02-r3.mp4','water-02-r3.mp4'];before={n:digest(P/n) for n in protected}
 shutil.copy2(F/'water-candidate.mp4',P/'water-02-r4.mp4');shutil.copy2(F/'poster.jpg',P/'water-r4-poster.jpg')
 page=(P/'index.html').read_text(encoding='utf-8');(O/'previous-player.html').write_text(page,encoding='utf-8')
 marker="const revised=new Set(['water','earth','lightning']),previous=document.getElementById('previous');let active='fire',showPrevious=false;"
 helpers="\nconst revisions={water:4,earth:3,lightning:3};\nfunction movieFor(name,prior=false){return revisions[name]?`${name}-02-r${revisions[name]-(prior?1:0)}.mp4`:`${name}-02.mp4`;}\nfunction posterFor(name,prior=false){return name==='fire'?'poster.jpg':revisions[name]?`${name}-r${revisions[name]-(prior?1:0)}-poster.jpg`:`${name}-poster.jpg`;}"
 assert marker in page;page=page.replace(marker,marker+helpers)
 page=page.replace("name==='fire'?'poster.jpg':revised.has(name)?`${name}-r3-poster.jpg`:`${name}-poster.jpg`",'posterFor(name)')
 page=page.replace("revised.has(name)?`${name}-02-r3.mp4`:`${name}-02.mp4`",'movieFor(name)')
 page=page.replace("showPrevious?`${active}-r2-poster.jpg`:`${active}-r3-poster.jpg`",'posterFor(active,showPrevious)')
 page=page.replace("showPrevious?`${active}-02-r2.mp4`:`${active}-02-r3.mp4`",'movieFor(active,showPrevious)')
 assert 'film.src=movieFor(name)' in page and 'film.src=movieFor(active,showPrevious)' in page
 (P/'index.html').write_text(page,encoding='utf-8');assert before=={n:digest(P/n) for n in protected}
 (O/'publication.json').write_text(json.dumps(dict(path=str(P/'water-02-r4.mp4'),sha256=a['sha256'],protected=before,previous='water-02-r3.mp4',userAccepted=False),indent=2));print('Published water r4; previous water and the other four elements are unchanged.')
if __name__=='__main__':
 if sys.argv[1]=='publish':raise SystemExit('Water-only publication was superseded. Use sigil_02_alive_publish.py for the reviewed three-element delivery.')
 {'preview':preview,'encode':encode,'audit':audit}[sys.argv[1]]()
