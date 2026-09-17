from pathlib import Path
import sys,subprocess,json,hashlib
import numpy as np,cv2
from PIL import Image,ImageDraw
B=Path(__file__).resolve().parent;P=B.parents[2]/'outputs/cybrdelic-type/elements/motion/bending'
def ff(args):subprocess.run(['ffmpeg','-v','error','-y','-threads','2']+args,check=True)
for kind in [a for a in sys.argv[1:] if not a.startswith('--')]:
    clip=B/f'{kind}-v5.mp4'
    if kind in ['earth','water'] and '--audit-only' not in sys.argv:
        folder=B/('water-final-frames' if kind=='water' else 'earth-frames')
        missing=[i for i in range(120) if not (folder/f'{i:04}.jpg').exists()];assert not missing,missing
        args=['-framerate','30','-i',str(folder/'%04d.jpg')]
        if kind=='earth':
            args+=['-i',str(P.parent/'earth-dust.mp4'),'-filter_complex_threads','2','-filter_complex','[0:v]format=gbrp[s];[1:v]format=gbrp[d];[s][d]blend=all_mode=screen:all_opacity=0.16,scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p']
        else:args+=['-vf','scale=1920:1080:in_range=full:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709']
        ff(args+['-frames:v','120','-an','-c:v','libx264','-threads','2','-preset','slow','-crf','15','-pix_fmt','yuv420p','-colorspace','bt709','-color_range','tv','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart',str(clip)])
    meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=width,height,avg_frame_rate,nb_frames:format=duration','-of','json',str(clip)],text=True));s=meta['streams'][0]
    assert (s['width'],s['height'],s['nb_frames'],s['avg_frame_rate'])==(1920,1080,'120','30/1');assert float(meta['format']['duration'])==4
    c=cv2.VideoCapture(str(clip));rows=[];keyframes={};poster={'earth':50,'fire':45,'air':45,'water':58,'lightning':39}[kind]
    for f in range(120):
        ok,im=c.read();assert ok
        lum=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY);corners=np.concatenate([im[:24,:24].reshape(-1),im[:24,-24:].reshape(-1)])
        rows.append(dict(frame=f,meanLuma=float(lum.mean()),corner=float(corners.mean()),cornerMedian=float(np.median(corners)),cornerBlackFraction=float(np.mean(corners<=1)),activePixels=int(np.count_nonzero(lum>12))))
        if f in [20,45,65,100,119,poster]:keyframes[f]=Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB))
    assert not c.read()[0];c.release()
    # A flying stone crosses the upper-right sample at earth frame 89.
    # Measure the remaining black background and report foreground crossings.
    assert max(x['cornerMedian'] for x in rows)<.1
    assert min(x['cornerBlackFraction'] for x in rows)>.8
    keyframes[poster].save(B/f'{kind}-v5.jpg',quality=95)
    sheet=Image.new('RGB',(1440,810));draw=ImageDraw.Draw(sheet)
    for i,f in enumerate([20,45,65,100,119,poster]):
        sheet.paste(keyframes[f].resize((480,270)),((i%3)*480,(i//3)*270));draw.text(((i%3)*480+10,(i//3)*270+10),f'{kind} {f/30:.2f}s',fill='white')
    sheet.save(B/f'{kind}-sequence.jpg',quality=93)
    report=dict(metadata=meta,decodedFrames=len(rows),sha256=hashlib.sha256(clip.read_bytes()).hexdigest(),cornerForegroundFrames=[x['frame'] for x in rows if x['corner']>=.1],rows=rows)
    (B/f'{kind}-validation.json').write_text(json.dumps(report,indent=2))
    print(kind,'120 frames verified; black top corners; review sheet and poster saved',flush=True)
