"""CPU decode, framing checks and a bounded contact sheet for a finished test."""
from pathlib import Path
import cv2, json, subprocess, sys
import numpy as np
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;B=R/'sigil-native';variant=sys.argv[1] if len(sys.argv)>1 else '01'
path=B/f'fire-{variant}-free.mp4';meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,avg_frame_rate:format=duration','-of','json',str(path)],text=True))
stream=meta['streams'][0];assert (stream['width'],stream['height'])==(1920,1080);assert int(stream['nb_frames'])==255
cap=cv2.VideoCapture(str(path));picked={30,75,120,150,195,240};sheet=Image.new('RGB',(1280,1140));draw=ImageDraw.Draw(sheet);records=[];n=0
while True:
 ok,frame=cap.read()
 if not ok:break
 rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB);small=cv2.resize(rgb,(640,360),interpolation=cv2.INTER_AREA);luma=small@np.array([.2126,.7152,.0722]);mask=luma>8;yy,xx=np.nonzero(mask)
 corners=np.concatenate([small[:12,:12].ravel(),small[:12,-12:].ravel(),small[-12:,:12].ravel(),small[-12:,-12:].ravel()])
 row={'frame':n,'meanLuma':float(luma.mean()),'litPixels':len(xx),'cornerMax':int(corners.max()),'bounds':None if not len(xx) else [int(xx.min()),int(yy.min()),int(xx.max()),int(yy.max())]};records.append(row)
 if n in picked:
  k=sorted(picked).index(n);x=k%2*640;y=k//2*380;sheet.paste(Image.fromarray(small),(x,y+20));draw.text((x+12,y+4),f'Fire {variant} / {n/30:.1f}s',fill=(190,190,190))
 n+=1
cap.release();assert n==255
sheet.save(B/f'fire-{variant}-free-review.jpg',quality=91)
report={'video':str(path),'metadata':meta,'decodedFrames':n,'maxCornerValue':max(q['cornerMax'] for q in records),'peakMeanLuma':max(q['meanLuma'] for q in records),'endMeanLuma':records[-1]['meanLuma'],'reviewFrames':sorted(picked),'frames':records,'visualStatus':'pending human/model inspection; pixel metrics alone are not an approval'}
(B/f'fire-{variant}-free-audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ['frames','metadata']}))
