from pathlib import Path
import subprocess,json,io,sys
from PIL import Image,ImageDraw
import numpy as np
root=Path(__file__).parent
variant=sys.argv[1]
video=root.parent/f'outputs/cybrdelic-brand-{variant}-fire.mp4'
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(video)]))['streams'][0]
assert (meta['width'],meta['height'],meta['nb_read_frames'])==(1920,1080,'450'),meta
subprocess.run(['ffmpeg','-v','error','-i',str(video),'-f','null','-'],capture_output=True,check=True)
times=[1.5,3,4.5,6,7.5,10.5,12,14.9]
board=Image.new('RGB',(1536,472),(15,15,15));draw=ImageDraw.Draw(board);bright=[]
for i,t in enumerate(times):
    data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(video),'-frames:v','1','-vf','scale=384:216','-f','image2pipe','-vcodec','png','-'])
    im=Image.open(io.BytesIO(data)).convert('RGB');x=i%4*384;y=i//4*236
    board.paste(im,(x,y));draw.text((x+8,y+219),f'{t}s',fill='white');bright.append(float(np.array(im,dtype=float).sum()))
board.save(root/f'brand-fire-{variant}-review.jpg',quality=94)
diagnostics=[]
for line in (root/f'brand-fire-{variant}.log').read_text().splitlines():
    try:r=json.loads(line)
    except:continue
    if 'gasInventory' in r:diagnostics.append(r)
report={'metadata':meta,'fullDecode':True,'brightnessAtSampleTimes':dict(zip(times,bright)),'endToHoldRatio':bright[-1]/max(1,bright[5]),'simulationDiagnostics':diagnostics}
assert report['endToHoldRatio']<.02,report
(root.parent/f'outputs/cybrdelic-brand-{variant}-verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'variant':variant,'metadata':meta,'endToHoldRatio':report['endToHoldRatio'],'review':str(root/f'brand-fire-{variant}-review.jpg')}))
