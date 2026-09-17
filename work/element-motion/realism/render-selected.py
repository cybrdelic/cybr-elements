from pathlib import Path
import subprocess
R=Path(__file__).resolve().parent;O=R.parent.parent.parent/'outputs/cybrdelic-type/elements/motion/subelements/realism-tests'
for kind in ['plants','metal']:
 print('START',kind,flush=True)
 with (R/(kind+'-full.log')).open('w',encoding='utf-8') as log:subprocess.run(['C:/Program Files/Blender Foundation/Blender 4.5/blender.exe','-b','-t','3','--python',str(R/(kind+'.py')),'--','--full'],stdout=log,stderr=subprocess.STDOUT,check=True)
 assert 'Traceback (most recent call last)' not in (R/(kind+'-full.log')).read_text(encoding='utf-8',errors='replace')
 assert all((R/(kind+'-frames')/f'{f:04}.png').exists() for f in range(120))
 subprocess.run(['ffmpeg','-loglevel','error','-y','-framerate','30','-i',str(R/(kind+'-frames')/'%04d.png'),'-c:v','libx264','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(O/(kind+'-test.mp4'))],check=True)
 print('FINISHED',kind,flush=True)
