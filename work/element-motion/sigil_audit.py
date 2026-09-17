from pathlib import Path
import json,sys,subprocess,hashlib
import numpy as np,cv2
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;B=R/'sigil-v1';element=sys.argv[1];variant=sys.argv[2];stem=f'{element}-{variant}';O=B/stem
frames=O/'frames';video=B/f'{stem}.mp4'
if frames.exists():
 names=sorted(p.name for p in frames.glob('*.jpg'));assert names==[f'{f:04}.jpg' for f in range(300)],(len(names),names[-3:])
 subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-i',str(frames/'%04d.jpg'),'-vf','scale=1920:1080:flags=lanczos,setsar=1','-c:v','libx264','-threads','2','-crf','16','-preset','fast','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],check=True)
q=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames,r_frame_rate:format=duration','-of','json',str(video)]))
s=q['streams'][0];assert (s['width'],s['height'],int(s['nb_read_frames']),s['r_frame_rate'])==(1920,1080,300,'30/1')
subprocess.run(['ffmpeg','-v','error','-i',str(video),'-f','null','-'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
cap=cv2.VideoCapture(str(video));chosen=[20,60,96,120,150,180,195,210,240,270,299];sheet=Image.new('RGB',(1440,810),(8,8,8));draw=ImageDraw.Draw(sheet);stats=[]
for i,f in enumerate(chosen):
 cap.set(cv2.CAP_PROP_POS_FRAMES,f);ok,bgr=cap.read();assert ok
 rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);im=Image.fromarray(rgb);im.thumbnail((1440,810));im.save(O/f'{f:04}.jpg',quality=94)
 small=im.resize((360,202));x=(i%4)*360;y=(i//4)*270;sheet.paste(small,(x,y+22));draw.text((x+8,y+5),f'{stem} / {f/30:.2f}s',fill=(190,190,190))
 corners=np.concatenate([rgb[:24,:24].ravel(),rgb[:24,-24:].ravel(),rgb[-24:,:24].ravel(),rgb[-24:,-24:].ravel()]);stats.append(dict(frame=f,cornerMean=float(corners.mean()),cornerMax=int(corners.max()),litPixels=int((rgb.max(2)>30).sum())))
cap.release();sheet.save(O/'timeline.jpg',quality=90)
audit=dict(element=element,variant=variant,metadata=q,bytes=video.stat().st_size,sha256=hashlib.sha256(video.read_bytes()).hexdigest(),samples=stats,decode='complete')
(O/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');print(json.dumps(dict(video=str(video),frames=300,bytes=video.stat().st_size,timeline=str(O/'timeline.jpg'),maxCorner=max(s['cornerMax'] for s in stats))))
