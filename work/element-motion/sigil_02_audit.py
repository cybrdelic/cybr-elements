from pathlib import Path
import json,subprocess,cv2,numpy as np
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;O=R/'sigil-02-v2';path=O/'fire-02.mp4'
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,avg_frame_rate:format=duration','-of','json',str(path)],text=True));s=meta['streams'][0]
assert (s['width'],s['height'],int(s['nb_frames']),s['avg_frame_rate'])==(1920,1080,294,'30/1'),meta
cap=cv2.VideoCapture(str(path));selected=[30,75,120,165,205,270];sheet=Image.new('RGB',(1280,1140));draw=ImageDraw.Draw(sheet);rows=[];count=0
while True:
 ok,bgr=cap.read()
 if not ok:break
 rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);small=cv2.resize(rgb,(640,360),interpolation=cv2.INTER_AREA);lum=small@np.array([.2126,.7152,.0722]);mask=lum>8;yy,xx=np.nonzero(mask)
 corners=np.concatenate([small[:12,:12].ravel(),small[:12,-12:].ravel(),small[-12:,:12].ravel(),small[-12:,-12:].ravel()]);border=np.concatenate([lum[0],lum[-1],lum[:,0],lum[:,-1]])
 rows.append({'frame':count,'meanLuma':float(lum.mean()),'cornerMax':int(corners.max()),'frameEdgeLumaMax':float(border.max()),'litPixels':int(len(xx)),'bounds':None if not len(xx) else [int(xx.min()),int(yy.min()),int(xx.max()),int(yy.max())]})
 if count in selected:
  i=selected.index(count);x=i%2*640;y=i//2*380;sheet.paste(Image.fromarray(small),(x,y+20));draw.text((x+12,y+4),f'02 / {count/30:.1f}s',fill=(180,180,180))
 count+=1
cap.release();assert count==294,count
sheet.save(O/'review.jpg',quality=93)
report={'metadata':meta,'decodedFrames':count,'maxCornerValue':max(q['cornerMax'] for q in rows),'maxFrameEdgeLuma':max(q['frameEdgeLumaMax'] for q in rows),'peakMeanLuma':max(q['meanLuma'] for q in rows),'endMeanLuma':rows[-1]['meanLuma'],'sourceGeometry':json.loads((O/'source-report.json').read_text()),'frames':rows,'visualStatus':'pending'}
(O/'audit.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['metadata','frames','sourceGeometry']}))
