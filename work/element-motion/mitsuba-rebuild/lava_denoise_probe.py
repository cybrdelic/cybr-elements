from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from cpu_oidn import denoise
from lava_render import mapped
R=Path(__file__).resolve().parent/'lava-focus/renders';a=np.load(R/'micro-probe-hero-0029-640-24spp-raw-aov.npz');hdr=a['color'];black=np.max(np.abs(hdr),axis=-1)==0
out=Image.new('RGB',(1280,430));d=ImageDraw.Draw(out)
for j,(label,albedo) in enumerate([('Color only',None),('Color and albedo',a['albedo'])]):
 clean=denoise(hdr,albedo);clean[black]=0;im=Image.fromarray((mapped(clean,7)*255).clip(0,255).astype('uint8'));out.paste(im,(640*j,30));d.text((640*j+12,10),label,fill='white')
out.save(R/'denoise-probe.png');print(str(R/'denoise-probe.png'))
