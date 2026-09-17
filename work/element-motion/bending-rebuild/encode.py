from pathlib import Path
import subprocess,sys,json
R=Path(__file__).resolve().parent
O=R.parents[2]/'outputs/cybrdelic-type/elements/motion/bending'
def run(args):subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y']+args,check=True)
for kind in sys.argv[1:]:
    frames=R/f'{kind}-frames'
    missing=[i for i in range(120) if not (frames/f'{i:04}.jpg').exists()]
    if missing:raise RuntimeError(f'{kind}: missing {missing[:10]}')
    args=['-framerate','30','-i',str(frames/'%04d.jpg')]
    if kind=='earth':
        args+=['-i',str(O.parent/'earth-dust.mp4'),'-filter_complex','[0:v]format=gbrp[s];[1:v]format=gbrp[d];[s][d]blend=all_mode=screen:all_opacity=0.22,format=yuv420p']
    else:args+=['-pix_fmt','yuv420p']
    run(args+['-frames:v','120','-c:v','libx264','-preset','slow','-crf','16','-movflags','+faststart',str(O/f'{kind}.mp4')])
    print(kind,'120 frames encoded',flush=True)
