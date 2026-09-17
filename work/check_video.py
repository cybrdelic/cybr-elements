import json, subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

root=Path(__file__).resolve().parent
video=root.parent/'outputs'/'cybrdelic-fire-intro.mp4'
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(video)],text=True))
stream=probe['streams'][0]
assert (stream['width'],stream['height'])==(1920,1080)
assert int(stream['nb_read_frames'])==225
assert stream['r_frame_rate']=='30/1'
frames=root/'decoded';frames.mkdir(exist_ok=True)
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(video),'-vf','fps=4,scale=640:360',str(frames/'%03d.jpg')],check=True)
files=sorted(frames.glob('*.jpg'));assert len(files)==30
sheet=Image.new('RGB',(1600,960),'#101012');draw=ImageDraw.Draw(sheet)
indices=[1,4,7,10,13,16,19,22,25,27,28,29]
for i,k in enumerate(indices):
    im=Image.open(files[k]).resize((400,225))
    x=(i%4)*400;y=(i//4)*320
    sheet.paste(im,(x,y+24));draw.text((x+10,y+265),f'{k/4:.2f} seconds',fill='white')
sheet.save(root/'review-contact.jpg',quality=90)
arr=[np.asarray(Image.open(p),dtype=np.float32) for p in files]
delta=[float(np.abs(b-a).mean()) for a,b in zip(arr,arr[1:])]
report={'probe':stream,'bytes':video.stat().st_size,'sampleCount':len(files),'adjacentSampleMeanDifferences':delta,'firstMean':float(arr[0].mean()),'lastMean':float(arr[-1].mean())}
(root/'video-check.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'frames':stream['nb_read_frames'],'dimensions':[stream['width'],stream['height']],'duration':stream['duration'],'bytes':video.stat().st_size,'review':str(root/'review-contact.jpg')}))
