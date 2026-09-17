from pathlib import Path
import subprocess,json,shutil,hashlib
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;O=R.parent.parent/'outputs';site=O/'cybrdelic-type/elements';report=json.loads((R/'audit.json').read_text())
for variant in ['01','02']:
 frames=R/f'production-{variant}';assert all((frames/f'{f:04}.jpg').exists() for f in range(192));cap=json.loads((R/f'production-capture-{variant}.json').read_text());assert not cap['errors']
 video=O/f'cybrdelic-water-{variant}-native.mp4'
 subprocess.run(['ffmpeg','-y','-v','error','-framerate','24','-i',str(frames/'%04d.jpg'),'-frames:v','192','-c:v','libx264','-crf','16','-preset','medium','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],check=True)
 meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames,duration,r_frame_rate','-of','json',str(video)]))['streams'][0]
 assert meta['width']==3840 and meta['height']==2160 and meta['nb_read_frames']=='192' and float(meta['duration'])==8
 shutil.copy2(video,site/f'water-{variant}-native.mp4');Image.open(frames/'0048.jpg').resize((1600,900)).save(site/f'water-{variant}-native.jpg',quality=94)
 sheet=Image.new('RGB',(1600,500),(16,22,29));d=ImageDraw.Draw(sheet)
 for j,f in enumerate([8,24,48,72,96,120,152,191]):
  x=j%4*400;y=j//4*250;sheet.paste(Image.open(frames/f'{f:04}.jpg').resize((400,225)),(x,y));d.text((x+8,y+230),f'{f/24:.2f}s',fill='white')
 sheet.save(O/f'cybrdelic-water-{variant}-native-review.jpg',quality=93)
 report['variants'][variant]['video']={**meta,'sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'webglErrors':cap['errors']}
 print('PACKAGED',variant,meta,flush=True)
(O/'cybrdelic-water-native-verification.json').write_text(json.dumps(report,indent=2))
