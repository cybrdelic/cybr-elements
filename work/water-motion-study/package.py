from pathlib import Path
import subprocess,json
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent
out=root.parent.parent/'outputs'; video=out/'cybrdelic-water-motion-study.mp4'
frames=[root/'frames'/f'{i:04}.png' for i in range(1,145)]
assert all(p.is_file() for p in frames)
subprocess.run(['ffmpeg','-y','-v','error','-framerate','24','-start_number','1','-i',str(root/'frames/%04d.png'),'-frames:v','144','-c:v','libx264','-preset','medium','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],check=True)
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames,duration,r_frame_rate','-of','json',str(video)]))
assert meta['streams'][0]['nb_read_frames']=='144'
sheet=Image.new('RGB',(1440,580),(12,17,21)); d=ImageDraw.Draw(sheet)
for j,frame in enumerate([16,40,64,88,112,144]):
 im=Image.open(frames[frame-1]).convert('RGB'); im.thumbnail((480,270));x=j%3*480;y=j//3*290;sheet.paste(im,(x,y));d.text((x+10,y+272),f'{(frame-1)/24:.2f}s',fill='white')
sheet.save(out/'cybrdelic-water-motion-study-review.jpg',quality=93)
(out/'cybrdelic-water-motion-study-verification.json').write_text(json.dumps(meta,indent=2))
print(str(video))
