"""Dark-field numerical schlieren from the solved three-dimensional heat field.
An optical visualization of index gradients, not emitted smoke or naked-eye air.
Reference: NASA Glenn Schlieren Flow Visualization.
"""
from pathlib import Path
import sys,json
import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image
R=Path(__file__).resolve().parent
selected=list(range(120)) if '--full' in sys.argv else list(map(int,sys.argv[sys.argv.index('--frames')+1].split(',')))
out=R/'frames/heat';out.mkdir(exist_ok=True)
for f in selected:
    fields=np.load(R/'cache/combustion'/f'{f:04}.npz')['fields'];temp=fields[0].astype('f4');Z,Y,X=temp.shape
    # Constant-pressure gas density scales inversely with absolute temperature.
    # The small-index-contrast ray approximation integrates through camera depth.
    index_contrast=.00027*(293/(293+500*np.maximum(0,temp))-1)
    optical_path=index_contrast.sum(axis=1)*(3/(Y-1));optical_path=gaussian_filter(optical_path,.65)
    dz,dx=np.gradient(optical_path,4.2/(Z-1),10.5/(X-1));angle=np.sqrt(dx*dx+dz*dz)
    signal=(1-np.exp(-np.maximum(0,angle-.000002)*3200))**1.4
    rgb=np.clip(signal[...,None]*np.array([.76,.84,.92])[None,None]*255,0,255).astype('u1')[::-1]
    im=Image.fromarray(rgb).resize((1920,768),Image.Resampling.LANCZOS);canvas=Image.new('RGB',(1920,1080));canvas.paste(im,(0,120));canvas.save(out/f'{f:04}.jpg',quality=97)
    if f%20==0:print('THERMAL OPTICS',f,flush=True)
(R/'heat-mechanism.json').write_text(json.dumps({'model':'small-angle dark-field numerical schlieren','input':'3D advected temperature field','outputFrames':selected,'limits':'Optical diagnostic with amplified sensitivity; not a claim that warm air is self-luminous','reference':'https://www.grc.nasa.gov/www/k-12/airplane/tunvschlrn.html'},indent=2),encoding='utf-8')
