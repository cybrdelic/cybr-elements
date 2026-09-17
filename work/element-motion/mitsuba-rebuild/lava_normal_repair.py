"""Re-denoise the cached lava beauty with a verified world-space normal pass."""
from pathlib import Path
import numpy as np
from PIL import Image
from cpu_oidn import denoise
from lava_render import mapped
R=Path(__file__).resolve().parent/'lava-focus/renders'
stem='v5-hero-0029-640-24spp'
a=np.load(R/f'{stem}-raw-aov.npz');normal=np.load(R/'v5-hero-0029-640-world-normal.npy')
hit=np.linalg.norm(normal,axis=-1)>.2
assert np.std(normal[hit],axis=0).max()>.15, 'The normal pass must describe changing surface orientation'
hdr=a['color'];clean=denoise(hdr,a['albedo'],normal);clean[np.max(np.abs(hdr),axis=-1)==0]=0
Image.fromarray((mapped(clean,7)*255).clip(0,255).astype('uint8')).save(R/f'{stem}-normal-fixed.png')
np.savez_compressed(R/f'{stem}-normal-fixed.npz',color=hdr,albedo=a['albedo'],normal=normal,denoised=clean)
preview=((normal*.5+.5)*255).clip(0,255).astype('uint8');preview[~hit]=0;Image.fromarray(preview).save(R/'world-normal-verified.png')
print('REPAIRED',str(R/f'{stem}-normal-fixed.png'));print('normal standard deviation',np.std(normal[hit],axis=0).tolist())
