from pathlib import Path
import json,subprocess,hashlib,shutil
from PIL import Image,ImageDraw
r=Path(__file__).resolve().parent;o=r.parent.parent/'outputs';video=o/'cybrdelic-water-01-flip-v2.mp4'
frames=[r/f'frames/{i:04}.png' for i in range(192)];assert all(f.exists() for f in frames)
subprocess.run(['ffmpeg','-y','-v','error','-framerate','24','-i',str(r/'frames/%04d.png'),'-frames:v','192','-c:v','libx264','-crf','15','-preset','medium','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],check=True)
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames,duration,r_frame_rate','-of','json',str(video)]))['streams'][0];assert meta['nb_read_frames']=='192' and meta['width']==1920
sheet=Image.new('RGB',(1440,580),(8,12,15));d=ImageDraw.Draw(sheet)
for j,k in enumerate([24,58,96,120,152,191]):
 im=Image.open(frames[k]).convert('RGB').resize((480,270));x=j%3*480;y=j//3*290;sheet.paste(im,(x,y));d.text((x+8,y+273),f'{k/24:.2f}s',fill='white')
sheet.save(o/'cybrdelic-water-01-flip-v2-review.jpg',quality=94)
(o/'cybrdelic-water-01-flip-v2-verification.json').write_text(json.dumps({'video':meta,'solver':'Original CYBR FLIP III.1','reconstruction':'Original DetailReconstruction','renderer':'Blender Cycles; not original raster optics','scene':'Custom paired moving emitters along approved 01 path','physicalSeconds':2,'playbackSeconds':8,'holdReleasePhysicalTime':1.25,'spray':'Tracked volume-preserving bounded Pareto subgrid breakup; art-directed','maximumBreakupVolumeError':max(x['breakupVolumeError'] for x in json.loads((r/'mesh-report.json').read_text())),'sourceHashes':json.loads((r.parent/'flip-lettering/source-verification.json').read_text())},indent=2))
shutil.copy2(video,o/'cybrdelic-type/elements/water-01-flip-v2.mp4')
print(video,meta)
