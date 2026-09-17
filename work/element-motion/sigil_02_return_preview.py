"""CPU editorial test: reuse the approved physical breakup as a reversed lift.

This is explicitly reversed simulated motion, not a newly solved forward intro.
The approved fall is preserved frame-for-frame as the second part of each clip.
"""
from pathlib import Path
import subprocess,json,sys
import cv2
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;O=R/'sigil-02-loose-arrival';O.mkdir(exist_ok=True)
P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
sources={'water':'water-02-r6.mp4','earth':'earth-02-r5.mp4'}
start=210
short='--short' in sys.argv
for e,name in sources.items():
 # Reverse just the last six seconds, into the already settled held mark.
 # A 30 fps exact-frame mapping avoids invented optical-flow motion.
 out=O/f'{e}-cpu{"-short" if short else ""}.mp4'
 end=331 if short else 390
 filt=f'[0:v]scale=960:540,split[a][b];[a]trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS,reverse[r];[b]trim=start_frame={start}:end_frame=390,setpts=PTS-STARTPTS[f];[r][f]concat=n=2:v=1:a=0[v]'
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(P/name),'-filter_complex',filt,'-map','[v]','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(out)],check=True)
 cap=cv2.VideoCapture(str(out));im=Image.new('RGB',(1280,760));d=ImageDraw.Draw(im)
 for i,f in enumerate([0,24,48,72] if short else [0,45,90,135]):
  cap.set(cv2.CAP_PROP_POS_FRAMES,f);ok,bgr=cap.read();assert ok
  im.paste(Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)).resize((640,360)),(i%2*640,i//2*380+20));d.text((i%2*640+10,i//2*380+3),f'{e} / {f/30:.1f}s',fill='white')
 cap.release();im.save(O/f'{e}-cpu{"-short" if short else ""}-review.jpg',quality=94)
 print(e,'CPU preview ready',flush=True)
(O/'study.json').write_text(json.dumps(dict(method='Reversed native simulated breakup, followed by the same original held state and forward fall.',newForwardSimulation=False,sources=sources,sourceFrames=[210,389],previewResolution=[960,540],fps=30,totalFrames=360,scope='Water and earth openings only; preserve accepted falls.',budget='Two CPU editorial tests, then one chosen full-resolution encode; no GPU rendering.'),indent=2))
