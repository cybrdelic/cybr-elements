"""Generate two circular gas-source paths for the existing Fire/Air consumer.

Only inflow geometry, arrival and tangent fields are authored here. Downstream
motion is still the shared collocated solver; no flow trajectory is prescribed.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def generate(destination):
    if destination.exists():raise FileExistsError('Preserve the existing source; choose a new path')
    lo=np.array([-7.,-.6,-1.05],np.float32)
    extent=np.array([14.,1.2,7.875],np.float32)
    x=np.linspace(lo[0],lo[0]+extent[0],896,dtype=np.float32)[None,:]
    z=np.linspace(lo[2],lo[2]+extent[2],504,dtype=np.float32)[:,None]
    distance=[]; arrival=[]; tangent_x=[]; tangent_z=[]
    for center,sign in ((-1.2,1),(1.2,-1)):
        dx,dz=x-center,z-2.45
        radius=np.sqrt(dx*dx+dz*dz)
        theta=np.arctan2(dz,dx)
        distance.append(np.abs(radius-1.6))
        arrival.append(.3+np.mod(sign*theta,2*np.pi)/(2*np.pi)*3.6)
        tangent_x.append(-sign*dz/np.maximum(radius,1e-6))
        tangent_z.append(sign*dx/np.maximum(radius,1e-6))
    select=distance[0]<=distance[1]
    sdf=.095-np.minimum(*distance)
    support=np.clip(sdf/.035,0,1)
    result=dict(support=support,sdf=sdf,
                arrival=np.where(select,arrival[0],arrival[1]),
                dirx=np.where(select,tangent_x[0],tangent_x[1]),
                dirz=np.where(select,tangent_z[0],tangent_z[1]),lo=lo,extent=extent)
    destination.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(destination,**{key:np.asarray(value,dtype=np.float32) for key,value in result.items()})
    receipt=dict(example='two counter-rotating circular source paths',grid=[896,504],
                 centers=[[-1.2,2.45],[1.2,2.45]],radius=1.6,halfWidth=.095,
                 edgeRamp=.035,arrivalStart=.3,arrivalSweepSeconds=3.6,
                 direction=[1,-1],sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                 consumer='existing style-02 Air or Fire step/render functions',
                 physics='unchanged ELEMENTS collocated flow; art-directed source, not calibrated combustion')
    destination.with_suffix('.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    generate(parser.parse_args().output)
