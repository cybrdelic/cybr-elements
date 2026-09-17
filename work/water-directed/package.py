from pathlib import Path
import json,subprocess,hashlib,shutil
from PIL import Image,ImageDraw
r=Path(__file__).resolve().parent;o=r.parent.parent/'outputs';video=o/'cybrdelic-water-01-directed.mp4'
frames=[r/f'frames/{i:04}.png' for i in range(240)];assert all(f.exists() for f in frames)
subprocess.run(['ffmpeg','-y','-v','error','-framerate','24','-i',str(r/'frames/%04d.png'),'-frames:v','240','-c:v','libx264','-crf','15','-preset','medium','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],check=True)
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames,duration,r_frame_rate','-of','json',str(video)]))['streams'][0];assert meta['nb_read_frames']=='240' and meta['width']==1920 and meta['height']==1080
sheet=Image.new('RGB',(1600,500),(15,20,23));d=ImageDraw.Draw(sheet)
for j,k in enumerate([12,35,62,96,124,155,185,239]):
 im=Image.open(frames[k]).convert('RGB').resize((400,225));x=j%4*400;y=j//4*250;sheet.paste(im,(x,y));d.text((x+8,y+232),f'{k/24:.2f}s',fill='white')
sheet.save(o/'cybrdelic-water-01-directed-review.jpg',quality=94)
check=json.loads((r/'simulation-check.json').read_text());mesh=json.loads((r/'mesh-report.json').read_text())
report={'video':meta,'simulation':check,'choreography':'Single gated source, soft external guidance, right-to-left release into an exiting stream','surface':'DetailReconstruction with sigma 0.6, 1.08h support, four smoothing passes','spray':'Original primary droplets; sparse passive secondary births gated by speed and local extension, bounded Pareto sizes, persistent motion and lifetimes; no fixed fragment clusters','render':'Cycles 48 samples, GPU denoising, 1080p','physicsSeconds':2.5,'screenSeconds':10,'maximumSecondaryParticles':max(x['whitewater'] for x in mesh),'sha256':hashlib.sha256(video.read_bytes()).hexdigest()}
(o/'cybrdelic-water-01-directed-verification.json').write_text(json.dumps(report,indent=2));shutil.copy2(video,o/'cybrdelic-type/elements/water-01-directed.mp4');print(str(video),meta)
