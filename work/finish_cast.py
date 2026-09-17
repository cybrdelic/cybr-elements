from pathlib import Path
import subprocess,numpy as np
root=Path(__file__).resolve().parent
src=root.parent/'outputs'/'cybrdelic-fire-cast.mp4';dst=root/'cast-finished.mp4'
w,h=1920,1080
x=np.arange(w)
left=np.clip((x-45)/150,0,1);left=left*left*(3-2*left)
right=np.clip((1840-x)/180,0,1);right=right*right*(3-2*right)
dec=subprocess.Popen(['ffmpeg','-v','error','-i',str(src),'-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','-','-an','-c:v','libx264','-preset','fast','-crf','15','-pix_fmt','yuv420p','-movflags','+faststart',str(dst)],stdin=subprocess.PIPE)
n=0
while True:
    data=dec.stdout.read(w*h*3)
    if not data:break
    assert len(data)==w*h*3
    t=n/30
    entrance=1-np.clip((t-1.65)/.2,0,1)
    release=np.clip((t-5.25)/.45,0,1)
    mask=(1-entrance*(1-left))*(1-release*(1-right))
    rgb=np.frombuffer(data,np.uint8).reshape(h,w,3)
    rgb=(rgb*mask[None,:,None]).astype(np.uint8)
    enc.stdin.write(rgb.tobytes());n+=1
enc.stdin.close()
assert dec.wait()==0 and enc.wait()==0 and n==210
src.write_bytes(dst.read_bytes())
print('Softened entry/exit exhaust edges; all 210 frames retained.')
