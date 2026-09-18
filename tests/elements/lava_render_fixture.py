"""Create a tiny closed lava surface fixture for the Blender material smoke test."""
from pathlib import Path
import argparse
import numpy as np
from elements_core.runtime import RunIdentity, atomic_npz

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'meshes').mkdir(exist_ok=True)
    verts=np.array([
        [-.36,-.11,.055],[ .36,-.11,.055],[ .36,.11,.055],[-.36,.11,.055],
        [-.30,-.09,.46 ],[ .30,-.09,.46 ],[ .30,.09,.46 ],[-.30,.09,.46 ],
    ],dtype=np.float32)
    faces=np.array([
        [0,2,1],[0,3,2],[4,5,6],[4,6,7],
        [0,1,5],[0,5,4],[1,2,6],[1,6,5],
        [2,3,7],[2,7,6],[3,0,4],[3,4,7],
    ],dtype=np.int32)
    temperature=np.array([1080,1180,1275,1375,1460,1530,1600,1325],dtype=np.float32)
    damage=np.array([.95,.75,.55,.35,.15,.30,.65,.90],dtype=np.float32)
    run=RunIdentity(
        a.out,
        {'floor':.032,'fixture':'closed tapered slab with resolved temperature/damage gradient'},
        {'fixtureSource':Path(__file__)},
    )
    atomic_npz(a.out/'meshes/0000.npz',vertices=verts,faces=faces,temperature=temperature,
               damage=damage,rest=verts.copy(),time=np.float64(0.))
    run.receipt('mesh-0000',[a.out/'meshes/0000.npz'],frame=0)

if __name__=='__main__':main()
