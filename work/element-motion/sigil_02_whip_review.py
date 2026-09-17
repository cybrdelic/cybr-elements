from pathlib import Path
import json,sys,subprocess,hashlib
import cv2,numpy as np
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;O=R/'sigil-02-water-whip';full='--full' in sys.argv
run=O/('full' if full else 'cpu');frames=run/('frames' if full else 'preview-frames')
movie=O/('water-candidate.mp4' if full else 'cpu-motion.mp4')
if '--encode' in sys.argv:
 if full:
  assert len(list(frames.glob('*.jpg')))==390
  inp=['-framerate','30','-i',str(frames/'%04d.jpg')]
 else:
  files=sorted(frames.glob('*.jpg'));assert len(files)==30
  listing=run/'frames.txt';listing.write_text(''.join(f"file '{p.resolve().as_posix()}'\nduration 0.2\n" for p in files))
  inp=['-f','concat','-safe','0','-i',str(listing)]
 subprocess.run(['ffmpeg','-v','error','-y',*inp,'-c:v','libx264','-threads','2','-preset','slow','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(movie)],check=True)
if '--sheet' in sys.argv or '--encode' in sys.argv:
 picks=[0,18,36,54,72,90,114,150] if not full else [0,18,36,54,72,90,120,210,288,389]
 sheet=Image.new('RGB',(1280,210*((len(picks)+1)//2)));draw=ImageDraw.Draw(sheet)
 for i,f in enumerate(picks):
  path=frames/f'{f:04}.jpg'
  if not path.exists():continue
  pic=Image.open(path);pic.thumbnail((640,185));x=i%2*640+(640-pic.width)//2;y=i//2*210+23;sheet.paste(pic,(x,y));draw.text((i%2*640+12,i//2*210+5),f'{f/30:.2f}s',fill='white')
 sheet.save(O/('full-review.jpg' if full else 'cpu-review.jpg'),quality=94)
if '--encode' in sys.argv:
 meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=width,height,nb_frames,avg_frame_rate:format=duration','-of','json',str(movie)],text=True));cap=cv2.VideoCapture(str(movie));n=0;deltas=[];last=None
 while True:
  ok,img=cap.read()
  if not ok:break
  small=cv2.resize(img,(480,270));deltas.append(float(np.abs(small.astype(float)-last).mean()) if last is not None else 0);last=small.astype(float);n+=1
 cap.release()
 native=json.loads((run/'particles/manifest.json').read_text());rows=native['frames']
 assert native.get('complete') and all(r['finite'] and r['pressure']['converged'] for r in rows)
 assert len({r['particles'] for r in rows})==1 and all(r['minHeightWorld']>=0 for r in rows)
 assert all(not r['capacityRejected'] and not r['solidViolations'] and not r['pressureFailures'] and abs(r['sourceVolumeBalance'])<1e-8 for r in rows)
 if full:assert n==390 and meta['streams'][0]['width']==1920
 audit=dict(decodedFrames=n,metadata=meta,nativeFrames=len(rows),nativeFinite=True,pressureConverged=True,particleCount=rows[0]['particles'],minHeight=min(r['minHeightWorld'] for r in rows),sha256=hashlib.sha256(movie.read_bytes()).hexdigest(),visualStatus='pending',userAccepted=False,frameDifferences=deltas)
 if full:
  meshes=[json.loads((run/f'mesh/{i:04}.json').read_text()) for i in range(390)]
  assert all(q['renderedSubgridDrops']==0 for q in meshes)
  audit.update(maxEncodedVolumeRelativeError=max(abs(q['encodedVolumeRelativeError']) for q in meshes),maxUnresolvedHoldFraction=max(q['unresolvedMarkerFraction'] for q in meshes[180:243]),finalUnresolvedFraction=meshes[-1]['unresolvedMarkerFraction'],finalFloorContacts=rows[-1]['floorContacts'],maxNativeSpeed=max(q['maxSpeed'] for q in rows),limitations='Authored bending accelerations; native FLIP pressure, transport, free surface and floor response. Unresolved spray markers remain in the simulation but are omitted from rendering; no bead cloud is added.')
 (O/('audit.json' if full else 'cpu-audit.json')).write_text(json.dumps(audit,indent=2));print(json.dumps({k:v for k,v in audit.items() if k not in ['metadata','frameDifferences']}))
