"""Delivery integrity checks and compact review images. Visual review remains separate."""
import hashlib,json,subprocess
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent
O=R.parents[2]/'outputs/cybrdelic-type/elements/motion/bending'
elements=['earth','fire','water','air','lightning']
sheet=Image.new('RGB',(1440,1450));draw=ImageDraw.Draw(sheet)
records=[]
for row,kind in enumerate(elements):
    path=O/f'{kind}.mp4'
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_frames,duration,codec_name,pix_fmt','-of','json',str(path)]))['streams'][0]
    assert (probe['width'],probe['height'])==(1920,1080),probe
    assert probe['nb_frames']=='120' and probe['r_frame_rate']=='30/1',probe
    assert abs(float(probe['duration'])-4)<.001,probe
    cap=cv2.VideoCapture(str(path));count=0;corner_max=0;corner_background=0;corner_crossings=[];active=0;means=[]
    while True:
        ok,frame=cap.read()
        if not ok:break
        corners=np.concatenate([frame[:24,:24].reshape(-1,3),frame[:24,-24:].reshape(-1,3),frame[-24:,:24].reshape(-1,3),frame[-24:,-24:].reshape(-1,3)])
        corner_max=max(corner_max,int(corners.max()))
        # A stone can legitimately cross a corner (visually checked at earth
        # frame 46). Measure the background majority without calling debris a
        # raised black level; retain maximums and crossings for audit.
        corner_background=max(corner_background,float(np.percentile(corners,95)))
        if corners.max()>8:corner_crossings.append(count)
        means.append(round(float(frame.mean()),5))
        active+=int(frame.max()>30)
        if count in [21,42,69]:
            col=[21,42,69].index(count)
            im=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)).resize((480,270),Image.Resampling.LANCZOS)
            sheet.paste(im,(col*480,row*290+20));draw.text((col*480+8,row*290+3),f'{kind.title()} / {count/30:.2f}s',fill='white')
        if count==39:
            Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)).resize((1280,720),Image.Resampling.LANCZOS).save(O/f'{kind}.jpg',quality=94)
        count+=1
    cap.release()
    assert count==120,(kind,count)
    assert corner_background<=8,(kind,'Raised corner background',corner_background)
    assert active>40,(kind,'Not enough visible action',active)
    records.append({'element':kind,'video':path.name,'metadata':probe,'decodedFrames':count,'activeFrames':active,'cornerMaxRGB':corner_max,'cornerBackground95RGB':corner_background,'cornerObjectCrossings':corner_crossings,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'frameMeanRGB':means})
sheet.save(R/'delivery-review.jpg',quality=94)
(R/'validation.json').write_text(json.dumps({'passed':True,'videos':records},indent=2))
print(json.dumps({'passed':True,'videos':[{'element':r['element'],'frames':r['decodedFrames'],'activeFrames':r['activeFrames'],'cornerMaxRGB':r['cornerMaxRGB'],'MB':round(r['bytes']/1e6,2)} for r in records],'review':str(R/'delivery-review.jpg')},indent=2))
