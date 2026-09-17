from pathlib import Path
import subprocess,json,io
from PIL import Image,ImageDraw
import numpy as np
root=Path(__file__).resolve().parent
v=root.parent/'outputs'/'cybrdelic-fire-cast.mp4'
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(v)]))
s=meta['streams'][0]
assert (s['width'],s['height'],s['nb_read_frames'])==(1920,1080,'210'),s
subprocess.run(['ffmpeg','-v','error','-i',str(v),'-f','null','-'],check=True,capture_output=True)
sheet=Image.new('RGB',(1536,472),(16,16,16));draw=ImageDraw.Draw(sheet)
for i,t in enumerate([.8,1.55,2.35,2.9,3.55,4.5,5.3,6.2]):
    data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(v),'-frames:v','1','-vf','scale=384:216','-f','image2pipe','-vcodec','png','-'])
    im=Image.open(io.BytesIO(data));x=(i%4)*384;y=(i//4)*236
    sheet.paste(im,(x,y));draw.text((x+8,y+218),f'{t:.2f}s',fill='white')
sheet.save(root/'cast-final-review.jpg',quality=94)
data=subprocess.check_output(['ffmpeg','-v','error','-ss','6.96','-i',str(v),'-frames:v','1','-vf','scale=384:216','-f','image2pipe','-vcodec','png','-'])
last=np.array(Image.open(io.BytesIO(data)))
assert last.max()<=3, int(last.max())
(root/'cast-verification.json').write_text(json.dumps({'video':meta,'lastFrameMax':int(last.max()),'allFramesDecoded':True},indent=2))
print(json.dumps({'metadata':s,'decode':'all frames passed','lastFrameMax':int(last.max()),'review':str(root/'cast-final-review.jpg')}))

