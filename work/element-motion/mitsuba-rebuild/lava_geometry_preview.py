"""Small CPU z-buffer diagnostic; no path tracing or GPU context."""
from pathlib import Path
import os,argparse,json
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='2')
import numpy as np
from numba import njit
from PIL import Image

@njit(cache=True)
def raster(p,f,color,w,h):
    image=np.zeros((h,w,3),np.uint8);depth=np.full((h,w),1e9)
    for k in range(len(f)):
        a,b,c=p[f[k]]
        lo=np.maximum(0,np.floor(np.minimum(a[:2],np.minimum(b[:2],c[:2])))).astype(np.int32)
        hi=np.minimum(np.array([w-1,h-1]),np.ceil(np.maximum(a[:2],np.maximum(b[:2],c[:2])))).astype(np.int32)
        den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den)<1e-8:continue
        for y in range(lo[1],hi[1]+1):
            for x in range(lo[0],hi[0]+1):
                u=((b[1]-c[1])*(x+.5-c[0])+(c[0]-b[0])*(y+.5-c[1]))/den
                v=((c[1]-a[1])*(x+.5-c[0])+(a[0]-c[0])*(y+.5-c[1]))/den
                if u<0 or v<0 or u+v>1:continue
                z=u*a[2]+v*b[2]+(1-u-v)*c[2]
                if z<depth[y,x]:depth[y,x]=z;image[y,x]=color[k]
    return image

def main(name):
    root=Path(__file__).resolve().parent/'lava-focus/cohesive'
    a=np.load(root/f'{name}.npz');v=a['v'];f=a['f'];n=a['normal'][f].mean(1);temp=a['temperature'][f].mean(1)
    eye=np.array([.82,-2.43,1.58]);target=np.array([-.17,0,.12]);forward=target-eye;forward/=np.linalg.norm(forward);right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward)
    q=(v-eye)@np.array([right,up,forward]).T;w=640;h=480;fl=w/(2*np.tan(np.deg2rad(35)/2));p=np.c_[w/2+fl*q[:,0]/q[:,2],h/2-fl*q[:,1]/q[:,2],q[:,2]]
    light=np.array([-.3,-.5,.8]);shade=.22+.78*np.maximum(0,n@light)
    cool=np.tile(np.array([.31,.32,.33]),(len(f),1))*shade[:,None]
    heat=np.clip((temp-1100)/300,0,1)
    hot=np.c_[np.minimum(1,.35+.8*heat),.04+.40*heat,.01+.02*heat]
    rgb=cool*(1-heat[:,None])+hot*heat[:,None]
    im=raster(p,f,(np.clip(rgb,0,1)**(1/2.2)*255).astype('u1'),w,h)
    path=root/f'{name}-geometry.png';Image.fromarray(im).save(path)
    print(json.dumps({'path':str(path),'size':[w,h],'device':'CPU','purpose':'geometry visibility only, not final material'}))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('name');main(ap.parse_args().name)
