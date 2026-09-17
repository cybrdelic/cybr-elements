"""Display transform for path-traced linear RGB; no bloom or added emission.

Stephen Hill's ACES RRT/ODT fit, from MJP's MIT-licensed BakingLab:
https://github.com/TheRealMJP/BakingLab/blob/master/BakingLab/ACES.hlsl
The full input/output colour transforms preserve a highlight shoulder;
the previous independent-channel fit could retain clipped red primaries.
This is a display approximation, not a full ACES colour-management pipeline.
"""
import numpy as np
INPUT=np.array([[.59719,.35458,.04823],[.07600,.90834,.01566],[.02840,.13383,.83777]])
OUTPUT=np.array([[1.60475,-.53108,-.07367],[-.10208,1.10813,-.00605],[-.00327,-.07276,1.07602]])

def display(linear,exposure=1):
    x=np.maximum(np.asarray(linear),0)*exposure
    v=x@INPUT.T
    y=(v*(v+.0245786)-.000090537)/(v*(.983729*v+.432951)+.238081)
    y=np.clip(y@OUTPUT.T,0,1)
    return np.where(y<=.0031308,12.92*y,1.055*y**(1/2.4)-.055)

if __name__=='__main__':
    from PIL import Image,ImageDraw
    from pathlib import Path
    p=Path('lava-focus/mpm/rebuild-30/cooled-front/frame-000750-surface-optics/linear.npz')
    a=np.load(p)['clean'];sheet=Image.new('RGB',(1440,510));draw=ImageDraw.Draw(sheet)
    for i,e in enumerate([6,30,80]):
        im=Image.fromarray((display(a,e)*255).astype('u1'));im.thumbnail((480,450));sheet.paste(im,(i*480,40));draw.text((i*480+16,16),f'Actual cached Mitsuba light / exposure {e}',fill='#bbb')
    sheet.save('lava-focus/mpm/rebuild-32/display-comparison.png')
    z=display(np.zeros((1,3)));r=display(np.repeat(np.geomspace(.0001,100,512)[:,None],3,axis=1))
    assert np.array_equal(z,np.zeros((1,3))) and np.min(np.diff(r,axis=0))>=-1e-8
    print('Display transform finite, black preserving and monotonic. Comparison saved.')
