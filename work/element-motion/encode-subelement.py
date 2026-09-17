from pathlib import Path
import sys,subprocess,json
R=Path(__file__).resolve().parent;kind=sys.argv[1];src=R/'subelements'/f'{kind}-frames';out=R.parent.parent/'outputs/cybrdelic-type/elements/motion/subelements';out.mkdir(exist_ok=True)
missing=[f for f in range(120) if not (src/f'{f:04}.jpg').exists()]
if missing:raise RuntimeError(f'{kind}: missing frames {missing[:8]}')
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate','30','-i',str(src/'%04d.jpg'),'-frames:v','120','-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(out/f'{kind}.mp4')],check=True)
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss','1.3','-i',str(out/f'{kind}.mp4'),'-frames:v','1',str(out/f'{kind}.jpg')],check=True)
print('ENCODED',kind,flush=True)
