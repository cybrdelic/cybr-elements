from pathlib import Path
import subprocess,json,sys,hashlib,time
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parent;OUT=R/'media';OUT.mkdir(exist_ok=True)
for key in sys.argv[1:]:
    paths=[R/'frames'/key/f'{f:04}.jpg' for f in range(450)]
    assert all(p.exists() and p.stat().st_size>400 for p in paths),(key,'missing frames')
    for p in paths:
        with Image.open(p) as im:assert im.size==(1920,1080),(p,im.size)
    # Decode representative source frames; empty corners must remain black.
    visible=[];corners=[]
    for f in [0,30,90,150,210,240,300,345,390,449]:
        a=np.array(Image.open(paths[f]));visible.append(int((a.max(2)>12).sum()));corners.append(min(float(c.mean()) for c in [a[:8,:8],a[:8,-8:],a[-8:,:8],a[-8:,-8:]]))
    assert max(visible)>2000,(key,'empty output')
    assert max(corners)<4,(key,'black stage violation',corners)
    movie=OUT/f'{key}.mp4'
    subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-framerate','30','-i',str(paths[0].parent/'%04d.jpg'),'-frames:v','450','-c:v','libx264','-threads','3','-preset','slow','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(movie)],check=True)
    raw=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,duration,r_frame_rate','-of','json',str(movie)]);meta=json.loads(raw)['streams'][0]
    assert meta['nb_frames']=='450' and meta['width']==1920 and meta['height']==1080 and abs(float(meta['duration'])-15)<.001,meta
    candidates=[240,241,242,243,244,245,246,247,248,249];poster=max(candidates,key=lambda f:np.array(Image.open(paths[f])).mean());im=Image.open(paths[poster]);im.thumbnail((960,540));im.save(OUT/f'{key}.jpg',quality=92)
    meta.update(id=key,sha256=hashlib.sha256(movie.read_bytes()).hexdigest(),blackCornerMeans=corners,visibleCounts=visible,frameDigest=hashlib.sha256(b''.join(hashlib.sha256(p.read_bytes()).digest() for p in paths)).hexdigest())
    (OUT/f'{key}.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print('ENCODED',key,'450 HD frames / 15s',flush=True)
