from pathlib import Path
import subprocess,json,io
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent
v=root.parent/'outputs'/'cybrdelic-fire-hq.mp4'
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(v)]))
s=meta['streams'][0]
assert (s['width'],s['height'],s['nb_read_frames'])==(1920,1080,'285'),s
subprocess.run(['ffmpeg','-v','error','-i',str(v),'-f','null','-'],check=True,capture_output=True)
sheet=Image.new('RGB',(1536,616),(18,18,18));draw=ImageDraw.Draw(sheet)
for i,t in enumerate([1.,2.5,4.,5.5,7.3,8.5]):
    data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(v),'-frames:v','1','-vf','scale=512:288','-f','image2pipe','-vcodec','png','-'])
    im=Image.open(io.BytesIO(data));x=(i%3)*512;y=(i//3)*308
    sheet.paste(im,(x,y));draw.text((x+8,y+290),f'{t:.2f}s',fill='white')
sheet.save(root/'fire-hq-review.jpg',quality=92)
(root/'fire-hq-verification.json').write_text(json.dumps(meta,indent=2))
print(json.dumps({'metadata':s,'decode':'all frames passed','review':str(root/'fire-hq-review.jpg')}))
