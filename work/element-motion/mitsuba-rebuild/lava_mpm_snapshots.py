"""Bounded CPU frame diagnostics in one fixed camera; no interpolated states."""
import argparse,json
import numpy as np
from lava_mpm import ROOT
from lava_mpm_clasts import surface
from lava_mpm_surface import image_surface

def main(name):
    folder=ROOT/name;camera=np.load(folder/'state-surface.npz');frames=[]
    for path in sorted(folder.glob('frame-*.npz')):
        if '-surface' in path.stem:continue
        surface(name,path.stem)
        image=image_surface(path.with_name(path.stem+'-surface.npz'),camera)
        frames.append(dict(time=float(np.load(path)['time']),image=str(image)))
    (folder/'snapshots.json').write_text(json.dumps(frames,indent=2));print(json.dumps(dict(frames=len(frames),camera='Fixed across all cached times',first=frames[0]['time'],last=frames[-1]['time'])))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='fractured-feed-18');a=p.parse_args();main(a.name)
