"""Create three closed lava material swatches for the Blender smoke test."""
from pathlib import Path
import argparse
import numpy as np
from elements_core.runtime import RunIdentity, atomic_npz

def cube(cx,temp,damage):
    x0,x1=cx-.19,cx+.19; y0,y1=-.105,.105; z0,z1=.055,.43
    v=np.array([[x0,y0,z0],[x1,y0,z0],[x1,y1,z0],[x0,y1,z0],
                [x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]],np.float32)
    f=np.array([[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],
                [1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]],np.int32)
    return v,f,np.full(8,temp,np.float32),np.full(8,damage,np.float32)

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True);(a.out/'meshes').mkdir(exist_ok=True)
    pieces=[cube(-.46,1060.,.96),cube(0.,1265.,.96),cube(.46,1530.,.10)]
    verts=[];faces=[];temps=[];damage=[];offset=0
    for v,f,t,d in pieces:
        verts.append(v);faces.append(f+offset);temps.append(t);damage.append(d);offset+=len(v)
    verts=np.concatenate(verts);faces=np.concatenate(faces);temps=np.concatenate(temps);damage=np.concatenate(damage)
    run=RunIdentity(a.out,{'floor':.032,'fixture':'left obsidian / center damaged cooling crust / right hot melt'},
                    {'fixtureSource':Path(__file__)})
    atomic_npz(a.out/'meshes/0000.npz',vertices=verts,faces=faces,temperature=temps,
               damage=damage,rest=verts.copy(),time=np.float64(0.))
    run.receipt('mesh-0000',[a.out/'meshes/0000.npz'],frame=0)

if __name__=='__main__':main()
