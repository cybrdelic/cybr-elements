from pathlib import Path
import subprocess,json
R=Path(__file__).resolve().parent;O=R.parent.parent/'outputs/cybrdelic-type/elements/motion'
def run(a):subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y']+a,check=True)
def encode(src,name,dust=False):
 missing=[i for i in range(120) if not (src/f'{i:04}.jpg').exists()]
 if missing:raise RuntimeError(f'{name}: missing {missing[:8]}')
 args=['-framerate','30','-i',str(src/'%04d.jpg')]
 if dust:args+=['-i',str(O/'earth-dust.mp4'),'-filter_complex','[0:v]format=gbrp[s];[1:v]format=gbrp[d];[s][d]blend=all_mode=screen:all_opacity=0.65,format=yuv420p']
 else:args+=['-pix_fmt','yuv420p']
 run(args+['-frames:v','120','-c:v','libx264','-preset','slow','-crf','17','-movflags','+faststart',str(O/(name+'.mp4'))])
 run(['-ss','1.3','-i',str(O/(name+'.mp4')),'-frames:v','1',str(O/(name+'-poster.jpg'))])
 print(name,'encoded',flush=True)
if __name__=='__main__':
 import sys
 if sys.argv[1]=='earth':encode(R/'earth-strata-frames','earth-strata',True)
 if sys.argv[1]=='water':encode(R/'water-optical-deep-frames','water-optical')
