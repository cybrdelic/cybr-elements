from pathlib import Path
import os,json
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1')
import numpy as np
from PIL import Image
from cpu_oidn import denoise
R=Path(__file__).resolve().parent/'lava-focus/renders';a=np.load(R/'stage-obsidian-hero-0000-640-8spp-raw-aov.npz');color=a['color'];clean=denoise(color)
b=np.maximum(clean*8.5,0);b=np.clip(b*(2.51*b+.03)/(b*(2.43*b+.59)+.14),0,1);b=np.where(b<=.0031308,b*12.92,1.055*b**(1/2.4)-.055)
Image.fromarray((b*255).astype('u1')).save(R/'obsidian-unguided.png');print(json.dumps({'path':str(R/'obsidian-unguided.png'),'meanDenoiseChange':float(np.abs(clean-color).mean()),'cornerMax':float(b[:20,:20].max())}))
