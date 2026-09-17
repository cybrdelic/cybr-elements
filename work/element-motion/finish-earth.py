from pathlib import Path
import time,subprocess
from PIL import Image,ImageDraw
R=Path(__file__).parent;O=R.parent.parent/'outputs/cybrdelic-type/elements/motion'
while not (R/'earth-packed-frames/0119.jpg').exists():time.sleep(.5)
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate','30','-i',str(R/'earth-packed-frames/%04d.jpg'),'-i',str(O/'earth-dust.mp4'),'-filter_complex','[0:v]format=gbrp[s];[1:v]format=gbrp[d];[s][d]blend=all_mode=screen:all_opacity=0.65,format=yuv420p','-c:v','libx264','-crf','17','-movflags','+faststart',str(O/'earth-packed.mp4')],check=True)
im=Image.new('RGB',(1600,500),'black')
for j,f in enumerate([20,30,50,80]):
 for row,video in enumerate(['earth-shared.mp4','earth-packed.mp4']):
  p=R/f'earth-final-{row}-{f}.jpg';subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(f/30),'-i',str(O/video),'-frames:v','1','-vf','scale=400:225',str(p)],check=True);im.paste(Image.open(p),(j*400,row*250));ImageDraw.Draw(im).text((j*400+8,row*250+226),('Previous' if row==0 else 'Reworked')+f' {f/30:.2f}s',fill='white')
im.save(R/'earth-packed-review.jpg')
print('Earth packed video and review ready')
