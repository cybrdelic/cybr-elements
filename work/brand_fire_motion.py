import os
from pathlib import Path
import numpy as np
VARIANT=os.environ.get('BRAND_VARIANT','01')
DATA=np.load(Path(__file__).parent/f'brand-fire-{VARIANT}.npz')
times=DATA['times'];points=DATA['points'];emit=DATA['emit']
WRITE=times[-1];START=.08;MODE='brand-'+VARIANT
def pose(t):
    elapsed=np.clip(t-START,0,WRITE)
    def point(e):return np.array([np.interp(e,times,points[:,k]) for k in range(2)])
    p=point(elapsed);v=(point(min(WRITE,elapsed+.015))-point(max(0,elapsed-.015)))/.03
    speed=np.linalg.norm(v);direction=v/max(speed,1e-8)
    on=float(np.interp(elapsed,times,emit)) if START<t<START+WRITE else 0.
    return p,direction,on,min(5.,speed)
def turn_rate(t):
    a=pose(t-.012)[1];b=pose(t+.012)[1]
    return np.clip(np.arctan2(a[0]*b[1]-a[1]*b[0],np.dot(a,b))/.024,-3,3)
