from pathlib import Path
import subprocess,json,hashlib,sys
from PIL import Image,ImageDraw
import numpy as np,cv2
R=Path(__file__).resolve().parent
for kind in sys.argv[1:]:
 folder=R/'frames'/kind;out=R/'media';out.mkdir(exist_ok=True);counts=[];black=[];digest=hashlib.sha256()
 for f in range(120):
  p=folder/f'{f:04}.jpg';assert p.exists(),p
  with Image.open(p) as im:
   assert im.size==(1920,1080);a=np.asarray(im);counts.append(int(np.any(a>20,axis=2).sum()));black.append(float(np.all(a<4,axis=2).mean()));assert min(a[:8,:8].max(),a[-8:,-8:].max())<5
  digest.update(p.read_bytes())
 assert min(black)>.50 and max(counts)>500
 receipt=R/'receipts'/f'{kind}.json'
 if receipt.exists():assert json.loads(receipt.read_text())['frameDigest']==digest.hexdigest(),'Frames do not match the fresh complete render receipt'
 movie=out/f'{kind}.mp4'
 subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-framerate','30','-i',str(folder/'%04d.jpg'),'-frames:v','120','-c:v','libx264','-threads','2','-preset','slow','-crf','15','-pix_fmt','yuv420p','-movflags','+faststart',str(movie)],check=True)
 info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,nb_frames,duration','-of','json',str(movie)]))['streams'][0]
 assert (info['width'],info['height'],info['avg_frame_rate'],info['nb_frames'])==(1920,1080,'30/1','120')
 cap=cv2.VideoCapture(str(movie));decoded=0;panels=[];selected=[10,20,30,45,57,65,80,95];previous=None;difference=[]
 while True:
  ok,frame=cap.read()
  if not ok:break
  small=cv2.resize(frame,(320,180))
  if previous is not None:difference.append(float(np.abs(small.astype(float)-previous).mean()))
  previous=small.astype(float)
  if decoded in selected:panels.append(Image.fromarray(cv2.cvtColor(small,cv2.COLOR_BGR2RGB)))
  decoded+=1
 cap.release();assert decoded==120 and max(difference)>.05
 sheet=Image.new('RGB',(1280,360));draw=ImageDraw.Draw(sheet)
 for i,panel in enumerate(panels):sheet.paste(panel,((i%4)*320,(i//4)*180));draw.text(((i%4)*320+8,(i//4)*180+8),str(selected[i]),fill='white')
 sheet.save(out/f'{kind}-motion-review.jpg',quality=91)
 best=int(np.argmax(counts));Image.open(folder/f'{best:04}.jpg').save(out/f'{kind}.jpg',quality=96)
 proof={**info,'id':kind,'sha256':hashlib.sha256(movie.read_bytes()).hexdigest(),'frameDigest':digest.hexdigest(),'decodedFrames':decoded,'minimumBlackFraction':min(black),'posterFrame':best,'selectedReviewFrames':selected,'maximumFrameDifference':max(difference),'status':'Technical checks pass; manual motion review is still required'}
 (out/f'{kind}.json').write_text(json.dumps(proof,indent=2));print('VERIFIED',kind,'120 decoded HD frames',flush=True)
