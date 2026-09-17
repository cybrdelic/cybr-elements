"""Encode and audit new films; publication requires explicit local review gates."""
from pathlib import Path
import json,subprocess,hashlib,sys,shutil
import cv2,numpy as np
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;O=R/'sigil-02-active-elements';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
def encode(kind):
 folder=O/('water-full' if kind=='water' else kind);frames=folder/'frames';n=240 if kind=='water' else 300
 assert all((frames/f'{i:04}.jpg').exists() for i in range(n))
 dest=O/f'{kind}-native.mp4' if kind=='water' else O/f'{kind}-candidate.mp4'
 subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-i',str(frames/'%04d.jpg'),'-frames:v',str(n),'-an','-c:v','libx264','-threads','2','-preset','slow','-crf','14','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],check=True)
 if kind=='water':
  # Preserve the existing loose floor-lift edit, then join the new forward
  # solver at the formed mark. This short editorial overlap is disclosed.
  filt='[0:v]trim=start_frame=0:end_frame=102,setpts=PTS-STARTPTS[a];[1:v]setpts=PTS-STARTPTS[b];[a][b]xfade=transition=fade:duration=0.20:offset=3.20,format=yuv420p[v]'
  subprocess.run(['ffmpeg','-v','error','-y','-i',str(P/'water-02-r7.mp4'),'-i',str(dest),'-filter_complex',filt,'-map','[v]','-an','-c:v','libx264','-threads','2','-preset','slow','-crf','14','-pix_fmt','yuv420p','-movflags','+faststart',str(O/'water-candidate.mp4')],check=True)
 audit(kind)
 # Only redundant render frames are consumed; the encoded film, sampled
 # native caches, all solver metrics, and representative originals remain.
 keep={0,30,66,102,120,144,150,180,192,219,228,239,258,294,299}
 for f in frames.glob('*.jpg'):
  if f.stem.isdigit() and int(f.stem) not in keep:
   assert f.resolve().parent==frames.resolve();f.unlink()
 print('Encoded and verified',kind,flush=True)
def audit(kind):
 movie=O/f'{kind}-candidate.mp4';meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,avg_frame_rate:format=duration','-of','json',str(movie)]));s=meta['streams'][0]
 assert(s['width'],s['height'],s['avg_frame_rate'])==(1920,1080,'30/1')
 n=int(s['nb_frames']);cap=cv2.VideoCapture(str(movie));picks=np.linspace(0,n-1,12).astype(int).tolist();sheet=Image.new('RGB',(1280,1200));draw=ImageDraw.Draw(sheet);rows=[];last=None
 for i in range(n):
  ok,bgr=cap.read();assert ok,(kind,i);small=cv2.resize(bgr,(320,180));gray=cv2.cvtColor(small,cv2.COLOR_BGR2GRAY);delta=float(np.abs(small.astype(float)-last).mean()) if last is not None else 0;last=small.astype(float)
  rows.append(dict(frame=i,meanLuma=float(gray.mean()),activePixels=int((gray>12).sum()),adjacentDifference=delta,cornerMax=int(max(gray[:10,:10].max(),gray[:10,-10:].max()))))
  if i in picks:
   index=picks.index(i);im=Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB));im.thumbnail((620,170));x=index%2*640;y=index//2*200;sheet.paste(im,(x+(640-im.width)//2,y+25));draw.text((x+8,y+5),f'{kind} / {i/30:.2f}s',fill='white')
  if i==int(n*.5):Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)).resize((1280,720)).save(O/f'{kind}-poster.jpg',quality=94)
 assert not cap.read()[0];cap.release();sheet.save(O/f'{kind}-review.jpg',quality=94)
 result=dict(element=kind,metadata=meta,decodedFrames=n,sha256=hashlib.sha256(movie.read_bytes()).hexdigest(),blackCorners=max(r['cornerMax'] for r in rows),visualStatus='pending',userAccepted=False,rows=rows)
 (O/f'{kind}-audit.json').write_text(json.dumps(result,indent=2));print(kind,n,'frames decoded',flush=True)
def publish(kinds=None):
 kinds=kinds or ['water','ice','lava','lightning'];checks={k:json.loads((O/f'{k}-audit.json').read_text()) for k in kinds}
 assert all(a['visualStatus']=='agent-reviewed' for a in checks.values())
 protected=['fire-02.mp4','air-02.mp4','earth-02-r6.mp4','water-02-r7.mp4','lightning-02-r4.mp4'];digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();before={n:digest(P/n) for n in protected}
 html=(P/'index.html').read_text(encoding='utf-8')
 if not (O/'previous-player.html').exists():(O/'previous-player.html').write_text(html,encoding='utf-8')
 assert 'const revisions={water:' in html and 'earth:6' in html
 versions={'water':8,'lightning':5};artifacts=json.loads((O/'publication.json').read_text())['artifacts'] if (O/'publication.json').exists() else {}
 for k in kinds:
  src=O/f'{k}-candidate.mp4';assert digest(src)==checks[k]['sha256'];movie=f'{k}-02-r{versions[k]}.mp4' if k in versions else f'{k}-02.mp4';poster=f'{k}-r{versions[k]}-poster.jpg' if k in versions else f'{k}-poster.jpg'
  if (P/movie).exists():assert digest(P/movie)==checks[k]['sha256']
  else:(P/movie).hardlink_to(src)
  shutil.copy2(O/f'{k}-poster.jpg',P/poster);artifacts[k]=movie
  if k=='water':html=html.replace('water:7,earth:6','water:8,earth:6')
  if k=='lightning':html=html.replace('earth:6,lightning:4','earth:6,lightning:5')
  if k in ['ice','lava'] and f'data-element="{k}"' not in html:
   anchor='lava' if k=='ice' and 'data-element="lava"' in html else 'lightning'
   html=html.replace(f'<button data-element="{anchor}"',f'<button data-element="{k}" aria-pressed="false">{k.title()}</button><button data-element="{anchor}"')
 (P/'index.html').write_text(html,encoding='utf-8');assert before=={n:digest(P/n) for n in protected}
 (O/'publication.json').write_text(json.dumps(dict(artifacts=artifacts,protected=before,userAccepted=False),indent=2));print('Published reviewed films:',', '.join(kinds),'; approved fire, air and earth preserved.')
if __name__=='__main__':
 if sys.argv[1]=='encode':encode(sys.argv[2])
 elif sys.argv[1]=='audit':audit(sys.argv[2])
 elif sys.argv[1]=='publish':publish(sys.argv[2:] or None)
