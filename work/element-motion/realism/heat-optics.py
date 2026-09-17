from pathlib import Path
import numpy as np
from scipy.ndimage import zoom,map_coordinates,gaussian_filter
from PIL import Image
R=Path(__file__).resolve().parent;bg=np.asarray(Image.open(R/'heat-background-frames/0000.jpg').convert('RGB'),dtype='f4');h,w=bg.shape[:2];yy,xx=np.mgrid[:h,:w].astype('f4');waves=np.load(R/'heat-waves.npz')['height'];out=R/'heat-frames';out.mkdir(exist_ok=True)
# Background-oriented refractive distortion, without a visible smoke density layer.
for f,T in enumerate(waves):
 field=np.zeros((h,w),dtype='f4');height=int(4.7*h/5.90625);width=int(9.5*w/10.5);temp=zoom(T[::-1],(height/T.shape[0],width/T.shape[1]),order=3);y0=int((4.85625-4.35)*h/5.90625);x0=(w-width)//2;field[y0:y0+height,x0:x0+width]=temp[:height,:width]
 dy,dx=np.gradient(gaussian_filter(field,1.0));dx*=180;dy*=180;coords=[yy+dy,xx+dx];rgb=np.stack([map_coordinates(bg[:,:,c],coords,order=1,mode='nearest') for c in range(3)],-1)
 Image.fromarray(np.uint8(np.clip(rgb,0,255))).save(out/f'{f:04}.jpg',quality=96)
print('120 refracted background frames')
