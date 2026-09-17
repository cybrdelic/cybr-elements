from pathlib import Path
import subprocess,numpy as np,json
root=Path(__file__).resolve().parent
src=root.parent/'outputs'/'cybrdelic-firebending-intro.mp4'
dst=root/'finished-intro.mp4'
w,h=1920,1080
# Optical falloff only above the lettering, concealing the finite exhaust boundary.
z=4.2-(np.arange(h)-120)/768*4.2
m=np.clip((3.8-z)/.7,0,1);m=m*m*(3-2*m)
dec=subprocess.Popen(['ffmpeg','-v','error','-i',str(src),'-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','-','-an','-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(dst)],stdin=subprocess.PIPE)
n=0
while True:
    data=dec.stdout.read(w*h*3)
    if not data:break
    assert len(data)==w*h*3
    a=np.frombuffer(data,np.uint8).reshape(h,w,3)
    a=(a*m[:,None,None]).astype(np.uint8)
    enc.stdin.write(a.tobytes());n+=1
enc.stdin.close()
assert dec.wait()==0 and enc.wait()==0 and n==195
src.write_bytes(dst.read_bytes())
report=json.loads((root/'cybrdelic-report.json').read_text())
report['closingMark']='Non-burning strokes revealed behind the moving nozzle; separate from the reacting gas.'
report['opticalFinish']='Smooth exhaust falloff above the word; no displacement or deformation of fire.'
(root/'cybrdelic-report.json').write_text(json.dumps(report,indent=2))
print(f'Finished {n} frames at 1920x1080.')
