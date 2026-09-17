from pathlib import Path
import subprocess,numpy as np,sys
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
from gesture_motion import pose
src=root.parent/'outputs'/'cybrdelic-fire-gesture.mp4';dst=root/'gesture-finished.mp4'
w,h=1920,1080
# Suppress the finite solver boundary during the departing stroke only.
dec=subprocess.Popen(['ffmpeg','-v','error','-i',str(src),'-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','-','-an','-c:v','libx264','-preset','fast','-crf','15','-pix_fmt','yuv420p','-movflags','+faststart',str(dst)],stdin=subprocess.PIPE)
n=0
while True:
    data=dec.stdout.read(w*h*3)
    if not data:break
    assert len(data)==w*h*3
    physical=n/24
    cam=np.mean([pose(physical+lag)[0][0] for lag in np.linspace(-1.2,.35,18)])
    wx=np.linspace(cam-3.2,cam+3.2,w)
    edge=np.clip((4.82-wx)/.95,0,1);edge=edge*edge*(3-2*edge)
    mix=np.clip((n/30-9.1)/.35,0,1)
    mask=1-mix*(1-edge)
    rgb=np.frombuffer(data,np.uint8).reshape(h,w,3)
    enc.stdin.write((rgb*mask[None,:,None]).astype(np.uint8).tobytes());n+=1
enc.stdin.close()
assert dec.wait()==0 and enc.wait()==0 and n==354
src.write_bytes(dst.read_bytes())
print('Finished departure-edge falloff; retained 354 frames.')
