from pathlib import Path
import subprocess,json,io
from PIL import Image,ImageDraw
import numpy as np
root=Path(__file__).resolve().parent
v=root.parent/'outputs'/'cybrdelic-fire-gesture.mp4'
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(v)]))
s=meta['streams'][0]
assert (s['width'],s['height'],s['nb_read_frames'])==(1920,1080,'354'),s
subprocess.run(['ffmpeg','-v','error','-i',str(v),'-f','null','-'],check=True,capture_output=True)
def grab(t,width=384):
    data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(v),'-frames:v','1','-vf',f'scale={width}:-2','-f','image2pipe','-vcodec','png','-'])
    return Image.open(io.BytesIO(data)).convert('RGB')
def sheet(times,path):
    im=Image.new('RGB',(1536,236*((len(times)+3)//4)),(16,16,16));d=ImageDraw.Draw(im)
    for i,t in enumerate(times):
        x=(i%4)*384;y=(i//4)*236
        im.paste(grab(t),(x,y));d.text((x+7,y+219),f'{t:.2f}s',fill='white')
    im.save(root/path,quality=94)
sheet([.7,1.6,2.5,3.8,5.2,6.8,8.5,10.1],'gesture-overview.jpg')
sheet([round(2.0+i*.10,2) for i in range(12)],'gesture-motion-review.jpg')
last=np.array(grab(11.76))
assert last.max()<=3,int(last.max())
(root/'gesture-verification.json').write_text(json.dumps({'video':meta,'lastFrameMax':int(last.max()),'allFramesDecoded':True,'motionReview':'2.0 to 3.1 seconds sampled every 0.1 seconds'},indent=2))
print(json.dumps({'metadata':s,'decode':'all frames passed','lastFrameMax':int(last.max()),'review':['gesture-overview.jpg','gesture-motion-review.jpg']}))
