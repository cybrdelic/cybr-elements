from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
source = Path(r'C:\Users\alexf\Documents\Codex\2026-09-04\re\work\cybrdelic.github.io\tools\bake-reactive-fire.py')
code = source.read_text().split('total=round((a.warmup+a.seconds)*a.fps)')[0]
code = code.replace("ROOT = Path(__file__).resolve().parents[1]", "ROOT = Path(__file__).resolve().parent")
code = code.replace("out = ROOT/'output'/a.name", "out = ROOT/'frames'")
code = code.replace('out.mkdir(exist_ok=True)', 'out.mkdir(exist_ok=True, parents=True)')
code = code.replace("if shutil.disk_usage(out).free < 12*1024**3: raise RuntimeError('12 GiB free-space reserve required')", "if shutil.disk_usage(out).free < 1024**3: raise RuntimeError('1 GiB reserve required for streamed MP4; no volume caches written')")
code = code.replace("else:\n    from bending_fire_moves import pose as gesture_pose", "else:\n    gesture_pose = None")
code = code.replace("lo=np.array([-1.2,-1.24,.15],np.float32)", "lo=np.array([-5.25,-.5,0],np.float32)")
code = code.replace("extent=np.array([183,103,223],np.float32)*(5.5/224)", "extent=np.array([10.5,1.,3.94],np.float32)")
code = code.replace("source=(source>.01)*source", """source=(source>.01)*source
from PIL import ImageFont, ImageFilter
font=ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf',180)
box=font.getbbox('cybrdelic')
mask=Image.new('L',(box[2]-box[0]+4,box[3]-box[1]+4))
ImageDraw.Draw(mask).text((2-box[0],2-box[1]),'cybrdelic',font=font,fill=255,stroke_width=1)
mask=mask.resize((int(X*.81),int(Z*.32)),Image.Resampling.LANCZOS)
plate=Image.new('L',(X,Z));plate.paste(mask,((X-mask.width)//2,int(Z*.53)))
plate.save(ROOT/'fuel-mask.png')
solid=np.asarray(plate).astype(np.float32)/255
eroded=np.asarray(plate.filter(ImageFilter.MinFilter(5 if X>=700 else 3))).astype(np.float32)/255
shaped=np.clip((solid-eroded)*.8+solid*.18,0,1)
fuel_mask=torch.from_numpy(shaped[::-1].copy()).to(device)
source=fuel_mask[:,None,:]*torch.exp(-(y/.065)**4)*.16
""")
code = code.replace("inject=(source*inlet*dt*35).clamp(0,1)", """reveal=((t-.35)/2.25*12.-6.)
        ignition=((reveal-x)/.22).clamp(0,1)
        release=max(0.,min(1.,(5.1-t)/.65))
        inject=(source*ignition*release*inlet*dt*35).clamp(0,1)""")
# Solver transport, reaction, pressure projection, vorticity and radiance are retained.
code += '''
import subprocess
import sys
FPS=30
DURATION=float(os.environ.get('INTRO_SECONDS','7.5'))
TOTAL=round(DURATION*FPS)
W,H=1920,1080
video=ROOT.parent/'outputs'/'cybrdelic-fire-intro.mp4'
video.parent.mkdir(exist_ok=True)
encoder=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],stdin=subprocess.PIPE)
def render(frame):
    rgb,sigma=radiance()
    atten=torch.exp(-sigma*h[1])
    transmission=torch.cat([torch.ones_like(atten[:,:1]),torch.cumprod(atten[:,:-1],dim=1)],dim=1)
    linear=(transmission[...,None]*rgb*(1-atten[...,None])/sigma[...,None].clamp_min(1e-6)).sum(1)
    # Upsample the volume integration in linear light, then optical glow.
    linear=F.interpolate(linear.permute(2,0,1).flip(1)[None],size=(720,1920),mode='bicubic',align_corners=False).clamp_min(0)
    blur=F.avg_pool2d(F.avg_pool2d(linear,21,stride=1,padding=10),21,stride=1,padding=10)
    linear=(linear+blur*.22)*.34
    linear=F.pad(linear,(0,0,155,205))
    # A short optical fade closes the shot after the source has extinguished.
    fade=max(0.,min(1.,(DURATION-frame/FPS)/.7)) if DURATION>6 else 1.
    linear=linear*fade
    im=((linear*(2.51*linear+.03))/(linear*(2.43*linear+.59)+.14)).clamp(0,1)
    im=torch.where(im<=.0031308,im*12.92,1.055*im.pow(1/2.4)-.055)
    pixels=(im[0].permute(1,2,0)*255).byte().cpu().numpy()
    encoder.stdin.write(pixels.tobytes())
    if frame%15==0 or frame==TOTAL-1:
        Image.fromarray(pixels).resize((1280,720),Image.Resampling.LANCZOS).save(out/f'{frame:04}.jpg',quality=91)
for frame in range(TOTAL):
    for sub in range(a.substeps):div=step((frame+sub/a.substeps)/FPS)
    if frame%FPS==0:
        if not torch.isfinite(state).all():raise RuntimeError('Nonfinite state')
        if torch.cuda.max_memory_allocated()>6.8*1024**3:raise RuntimeError('GPU memory budget exceeded')
        print(json.dumps({'frame':frame,'total':TOTAL,'elapsed':round(time.monotonic()-started,1),'gpuMiB':round(torch.cuda.max_memory_allocated()/1048576),'divergence':div}),flush=True)
    render(frame)
encoder.stdin.close()
if encoder.wait()!=0:raise RuntimeError('Encoding failed')
(ROOT/'render-report.json').write_text(json.dumps({'frames':TOTAL,'fps':FPS,'size':[W,H],'solverGrid':a.size,'elapsed':time.monotonic()-started,'peakGpuMiB':torch.cuda.max_memory_allocated()/1048576,'source':'bake-reactive-fire.py','changes':'Letter-shaped fuel inlet with left-to-right ignition; original transport, combustion, vorticity, pressure and radiance; linear-light bloom.'},indent=2))
print(str(video),flush=True)
'''
(ROOT/'render_intro.py').write_text(code)
(ROOT/'source-sha256.txt').write_text(hashlib.sha256(source.read_bytes()).hexdigest())
print(ROOT/'render_intro.py')
