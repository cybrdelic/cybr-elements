"""CPU-only image output for NumPy volume integrators."""
from pathlib import Path
import os,json,time,hashlib
from PIL import Image
def save_image(image,kind,frame,seconds):
 out=Path(os.environ['CYBR_CPU_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
 # Same diagnostic camera as Cycles: 5.5 world units wide at x=.45,z=1.9.
 sx=image.width/10.5;cx=(.45+5.25)*sx;cy=(4.85625-1.9)*sx;w=5.5*sx;h=w*.75
 im=image.crop((round(cx-w/2),round(cy-h/2),round(cx+w/2),round(cy+h/2))).resize((512,384),Image.Resampling.LANCZOS)
 path=out/f'{kind}-{frame:04}.png';im.save(path)
 path.with_suffix('.json').write_text(json.dumps({'kind':kind,'frame':frame,'device':'CPU','denoiser':'none','denoisingGPU':False,'threads':2,'size':list(im.size),'seconds':round(seconds,3),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'purpose':'CPU diagnostic still, not production acceptance'},indent=2))
