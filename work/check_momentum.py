import json, subprocess
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent
video=root.parent/'outputs'/'cybrdelic-fire-momentum.mp4'
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(video)],text=True))['streams'][0]
assert (probe['width'],probe['height'])==(1920,1080)
assert probe['r_frame_rate']=='30/1' and int(probe['nb_read_frames'])==195
folder=root/'momentum-decoded';folder.mkdir(exist_ok=True)
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(video),'-vf','fps=5,scale=960:540',str(folder/'%03d.jpg')],check=True)
files=sorted(folder.glob('*.jpg'))
sheet=Image.new('RGB',(1600,810),'#101012');draw=ImageDraw.Draw(sheet)
for i,k in enumerate([1,3,5,8,10,13,15,17,19,22,26,30]):
    im=Image.open(files[k]);im=im.resize((400,225))
    x=i%4*400;y=i//4*270;sheet.paste(im,(x,y));draw.text((x+8,y+240),f'{k/5:.1f}s',fill='white')
sheet.save(root/'momentum-final-contact.jpg',quality=93)
arr=[np.asarray(Image.open(p),dtype=np.float32) for p in files]
deltas=[float(np.abs(b-a).mean()) for a,b in zip(arr,arr[1:])]
assert min(deltas[4:22])>.05,'Unexpected frozen interval'
report={'probe':probe,'bytes':video.stat().st_size,'sampledFrames':len(files),'minimumActiveIntervalChange':min(deltas[4:22]),'finalMeanLuma':float(arr[-1].mean())}
(root/'momentum-video-check.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
