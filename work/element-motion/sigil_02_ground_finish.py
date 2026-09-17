"""Review and deliver the two grounded bending revisions; preserve all others."""
from pathlib import Path
import json,sys,subprocess,hashlib,shutil
import cv2,numpy as np
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;O=R/'sigil-02-bending-ground';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def encode(element):
 folder=O/('full/frames' if element=='water' else 'earth-frames')
 assert [p.name for p in sorted(folder.glob('*.jpg'))]==[f'{i:04}.jpg' for i in range(390)]
 movie=O/f'{element}-candidate.mp4'
 subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-i',str(folder/'%04d.jpg'),'-c:v','libx264','-threads','2','-preset','slow','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(movie)],check=True)
 audit(element)
def audit(element):
 movie=O/f'{element}-candidate.mp4'
 meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,avg_frame_rate:format=duration','-of','json',str(movie)],text=True));s=meta['streams'][0]
 assert (s['width'],s['height'],int(s['nb_frames']),s['avg_frame_rate'])==(1920,1080,390,'30/1')
 picks=[0,42,90,120,180,246,276,300,330,389];im=Image.new('RGB',(1280,190*5));draw=ImageDraw.Draw(im);cap=cv2.VideoCapture(str(movie));rows=[];last=None;f=0
 while True:
  ok,bgr=cap.read()
  if not ok:break
  rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);small=cv2.resize(rgb,(640,360));top=np.concatenate([small[:8,:8].ravel(),small[:8,-8:].ravel()])
  rows.append(dict(frame=f,topCornerMax=int(top.max()),meanLuma=float(small.mean()),difference=float(np.abs(small.astype(float)-last).mean()) if last is not None else 0));last=small.astype(float)
  if f in picks:
   i=picks.index(f);x=i%2*640;y=i//2*190;picture=Image.fromarray(rgb);picture.thumbnail((640,168));im.paste(picture,(x+(640-picture.width)//2,y+20));draw.text((x+12,y+4),f'{element.upper()} / {f/30:.2f}s',fill=(200,200,200));Image.fromarray(rgb).resize((1280,720)).save(O/f'{element}-decoded-{f:04}.jpg',quality=94)
  if f==180:Image.fromarray(rgb).resize((1280,720)).save(O/f'{element}-poster.jpg',quality=95)
  f+=1
 cap.release();assert f==390;im.save(O/f'{element}-review.jpg',quality=94)
 report=dict(element=element,frames=f,metadata=meta,sha256=digest(movie),visualStatus='pending',userAccepted=False,rows=rows)
 if element=='water':
  native=json.loads((O/'full/particles/manifest.json').read_text());a=native['frames'];assert native['complete'] and len(a)==390
  assert all(r['finite'] and r['pressure']['converged'] and not r['capacityRejected'] and abs(r['sourceVolumeBalance'])<1e-8 for r in a)
  assert len({r['particles'] for r in a})==1 and all(r['minHeightWorld']>=0 for r in a)
  meshes=[]
  for f in range(390):
   path=O/f'full/mesh/{f:04}.json';row=json.loads(path.read_text())
   # This running mesher loaded the legacy diagnostic guide before its origin
   # correction. Discard that unused proximity statistic; geometry, pressure,
   # velocity and unresolved-marker measurements do not use the guide tree.
   row.pop('fractionInsideTwiceGuideRadius',None);path.write_text(json.dumps(row));meshes.append(row)
  report.update(nativeFinite=True,pressureConverged=True,closedMassCount=a[0]['particles'],finalFloorContacts=a[-1]['floorContacts'],minNativeHeight=min(r['minHeightWorld'] for r in a),maxUnresolvedHoldFraction=max(r['unresolvedMarkerFraction'] for r in meshes[165:243]),finalUnresolvedFraction=meshes[-1]['unresolvedMarkerFraction'])
 else:
  native=json.loads((O/'earth-report.json').read_text());assert all(r['finite'] for r in native['rows']);report.update(bodies=native['pieces'],nativeFinite=True,finalNearFloor=native['rows'][-1]['nearFloor'])
 (O/f'{element}-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['rows','metadata']}))
def publish():
 audits={e:json.loads((O/f'{e}-audit.json').read_text()) for e in ['water','earth']}
 for e,a in audits.items():assert a['visualStatus']=='agent-reviewed-improvement' and digest(O/f'{e}-candidate.mp4')==a['sha256']
 protected=['fire-02.mp4','air-02.mp4','lightning-02-r4.mp4','water-02-r4.mp4','earth-02-r4.mp4'];before={n:digest(P/n) for n in protected}
 for e in audits:shutil.copy2(O/f'{e}-candidate.mp4',P/f'{e}-02-r5.mp4');shutil.copy2(O/f'{e}-poster.jpg',P/f'{e}-r5-poster.jpg')
 page=(P/'index.html').read_text(encoding='utf-8');(O/'previous-player.html').write_text(page,encoding='utf-8');assert 'const revisions={water:4,earth:4,lightning:4}' in page
 page=page.replace('const revisions={water:4,earth:4,lightning:4}','const revisions={water:5,earth:5,lightning:4}');(P/'index.html').write_text(page,encoding='utf-8')
 assert before=={n:digest(P/n) for n in protected}
 report=dict(status='published-for-review',userAccepted=False,preserved=before,artifacts={e:dict(path=str(P/f'{e}-02-r5.mp4'),sha256=a['sha256']) for e,a in audits.items()})
 (O/'publication.json').write_text(json.dumps(report,indent=2));print('Published water and earth r5. r4 comparisons and fire, air, lightning preserved.')
if __name__=='__main__':
 if sys.argv[1]=='publish':publish()
 elif sys.argv[1]=='encode':encode(sys.argv[2])
 elif sys.argv[1]=='audit':audit(sys.argv[2])
