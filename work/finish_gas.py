from pathlib import Path
import subprocess,numpy as np,sys
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root))
from gesture_motion import pose
src=root.parent/'outputs'/'cybrdelic-gas-trail.mp4';dst=root/'gas-finished.mp4'
w,h=1920,1080
vertical=np.clip(np.arange(h)/85,0,1);vertical=vertical*vertical*(3-2*vertical)
dec=subprocess.Popen(['ffmpeg','-v','error','-i',str(src),'-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','-','-an','-c:v','libx264','-preset','fast','-crf','15','-pix_fmt','yuv420p','-movflags','+faststart',str(dst)],stdin=subprocess.PIPE)
n=0
while True:
    data=dec.stdout.read(w*h*3)
    if not data:break
    assert len(data)==w*h*3
    t=n/30;physical=n/16
    following=np.mean([pose(physical+lag)[0][0] for lag in np.linspace(-1.2,.35,18)])
    zoom=np.clip((t-5.55)/1.9,0,1);zoom=zoom*zoom*(3-2*zoom)
    cx=following*(1-zoom);width=6.4+5*zoom
    wx=np.linspace(cx-width/2,cx+width/2,w)
    edge=np.clip((4.82-wx)/.95,0,1);edge=edge*edge*(3-2*edge)
    mix=np.clip((t-6.5)/.35,0,1)
    horizontal=1-mix*(1-edge)
    im=np.frombuffer(data,np.uint8).reshape(h,w,3)
    enc.stdin.write((im*vertical[:,None,None]*horizontal[None,:,None]).astype(np.uint8).tobytes());n+=1
enc.stdin.close()
assert dec.wait()==0 and enc.wait()==0 and n==300
src.write_bytes(dst.read_bytes())
print('Finished optical edge falloff; retained 300 frames.')
