from pathlib import Path
import subprocess,json,io
from PIL import Image,ImageDraw
import numpy as np
root=Path(__file__).resolve().parent
v=root.parent/'outputs'/'cybrdelic-gas-trail.mp4'
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(v)]))
s=meta['streams'][0]
assert (s['width'],s['height'],s['nb_read_frames'])==(1920,1080,'300'),s
subprocess.run(['ffmpeg','-v','error','-i',str(v),'-f','null','-'],check=True,capture_output=True)
def grab(t,width=384):
    data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(v),'-frames:v','1','-vf',f'scale={width}:-2','-f','image2pipe','-vcodec','png','-'])
    return Image.open(io.BytesIO(data)).convert('RGB')
sheet=Image.new('RGB',(1536,472),(16,16,16));draw=ImageDraw.Draw(sheet)
for i,t in enumerate([1.5,3.,5.,6.3,7.5,8.,8.5,9.2]):
    x=(i%4)*384;y=(i//4)*236
    sheet.paste(grab(t),(x,y));draw.text((x+7,y+219),f'{t:.2f}s',fill='white')
sheet.save(root/'gas-final-review.jpg',quality=94)
before=np.asarray(grab(7.8),dtype=float)
after=np.asarray(grab(9.2),dtype=float)
ratio=float(after.sum()/max(1,before.sum()))
last=np.array(grab(9.96))
assert last.max()<=3,int(last.max())
assert ratio<.15,ratio
(root/'gas-verification.json').write_text(json.dumps({'video':meta,'allFramesDecoded':True,'extinctionBrightnessRatio':ratio,'lastFrameMax':int(last.max())},indent=2))
print(json.dumps({'metadata':s,'decode':'all frames passed','extinctionBrightnessRatio':round(ratio,4),'lastFrameMax':int(last.max()),'review':'gas-final-review.jpg'}))
