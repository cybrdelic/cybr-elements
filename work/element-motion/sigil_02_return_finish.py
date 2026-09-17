"""CPU-only reversed-simulation entrances, with accepted endings preserved.

This is a documented edit of existing native FLIP/Bullet renders, not a new
forward simulation. Source-frame mapping is audited against every output frame.
"""
from pathlib import Path
import json,subprocess,hashlib,sys,shutil,time
import cv2,numpy as np
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;O=R/'sigil-02-loose-arrival';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
sources={'water':'water-02-r6.mp4','earth':'earth-02-r5.mp4'}
versions={'water':7,'earth':6}
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
mapping=list(range(330,209,-1))+list(range(211,390))
assert len(mapping)==300 and mapping[153:]==list(range(243,390))
def encode(e):
 out=O/f'{e}-candidate.mp4'
 filt='[0:v]split[a][b];[a]trim=start_frame=210:end_frame=331,setpts=PTS-STARTPTS,reverse[r];[b]trim=start_frame=211:end_frame=390,setpts=PTS-STARTPTS[f];[r][f]concat=n=2:v=1:a=0[v]'
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(P/sources[e]),'-filter_complex',filt,'-map','[v]','-an','-c:v','libx264','-threads','2','-preset','slow','-crf','14','-pix_fmt','yuv420p','-movflags','+faststart',str(out)],check=True)
 audit(e)
def audit(e):
 out=O/f'{e}-candidate.mp4';source=P/sources[e]
 meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,avg_frame_rate:format=duration','-of','json',str(out)],text=True));s=meta['streams'][0]
 assert (s['width'],s['height'],s['nb_frames'],s['avg_frame_rate'])==(1920,1080,'300','30/1')
 original=cv2.VideoCapture(str(source));reference=[]
 while True:
  ok,img=original.read()
  if not ok:break
  reference.append(cv2.resize(img,(480,270)))
 original.release();assert len(reference)==390
 cap=cv2.VideoCapture(str(out));rows=[];picks=[0,24,48,72,96,145,165,195,240,299];im=Image.new('RGB',(1280,950));d=ImageDraw.Draw(im);last=None
 for f in range(300):
  ok,img=cap.read();assert ok
  small=cv2.resize(img,(480,270));ref=reference[mapping[f]];mse=float(np.mean((small.astype(float)-ref)**2));delta=float(np.abs(small.astype(float)-last).mean()) if last is not None else 0;last=small.astype(float)
  rows.append(dict(frame=f,sourceFrame=mapping[f],psnr=10*np.log10(255**2/max(mse,1e-12)),meanAbsoluteDifference=float(np.abs(small.astype(float)-ref).mean()),adjacentDifference=delta))
  if f in picks:
   i=picks.index(f);pic=Image.fromarray(cv2.cvtColor(img,cv2.COLOR_BGR2RGB));pic.thumbnail((640,168));im.paste(pic,(i%2*640+(640-pic.width)//2,i//2*190+22));d.text((i%2*640+12,i//2*190+4),f'{e} / {f/30:.2f}s',fill='white')
  if f==145:Image.fromarray(cv2.cvtColor(img,cv2.COLOR_BGR2RGB)).resize((1280,720)).save(O/f'{e}-poster.jpg',quality=95)
 assert not cap.read()[0];cap.release();im.save(O/f'{e}-review.jpg',quality=94)
 fall=rows[153:]
 # A source-frame match proves preservation of the physical fall; encode
 # compression is measured separately rather than described as bit-identical.
 assert min(q['psnr'] for q in rows)>38 and max(q['meanAbsoluteDifference'] for q in rows)<1.5
 report=dict(element=e,method='Reverse playback of existing native simulated breakup, then the original held state and falling motion.',newForwardSimulation=False,gpuUsed=False,source=str(source),sourceSha256=digest(source),sha256=digest(out),metadata=meta,frames=300,fallSourceFrames=[243,389],fallOutputFrames=[153,299],fallPreservedFrameForFrame=True,minFallPSNR=min(q['psnr'] for q in fall),maxFallMeanAbsoluteDifference=max(q['meanAbsoluteDifference'] for q in fall),visualStatus='pending',userAccepted=False,rows=rows)
 (O/f'{e}-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['rows','metadata','source','method']}),flush=True)
def publish():
 audits={e:json.loads((O/f'{e}-audit.json').read_text()) for e in sources}
 for e,a in audits.items():assert a['visualStatus']=='agent-reviewed-improvement' and digest(O/f'{e}-candidate.mp4')==a['sha256']
 protected=['fire-02.mp4','air-02.mp4','lightning-02-r4.mp4',*sources.values()];before={n:digest(P/n) for n in protected}
 page=(P/'index.html').read_text(encoding='utf-8');assert 'const revisions={water:6,earth:5,lightning:4}' in page
 (O/'previous-player.html').write_text(page,encoding='utf-8')
 for e,v in versions.items():shutil.copy2(O/f'{e}-candidate.mp4',P/f'{e}-02-r{v}.mp4');shutil.copy2(O/f'{e}-poster.jpg',P/f'{e}-r{v}-poster.jpg')
 (P/'index.html').write_text(page.replace('const revisions={water:6,earth:5,lightning:4}','const revisions={water:7,earth:6,lightning:4}'),encoding='utf-8')
 assert before=={n:digest(P/n) for n in protected}
 (O/'publication.json').write_text(json.dumps(dict(status='published-for-review',userAccepted=False,preserved=before,artifacts={e:dict(path=str(P/f'{e}-02-r{versions[e]}.mp4'),sha256=a['sha256']) for e,a in audits.items()}),indent=2));print('Published water r7 and earth r6; original falls and previous media preserved.')
if __name__=='__main__':
 if sys.argv[1]=='publish':publish()
 elif sys.argv[1]=='encode':encode(sys.argv[2])
 elif sys.argv[1]=='audit':audit(sys.argv[2])
