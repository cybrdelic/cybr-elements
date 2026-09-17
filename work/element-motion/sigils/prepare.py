"""Prepare the unchanged, approved 01/02 artwork for material source geometry."""
from pathlib import Path
import json,hashlib
import numpy as np
from scipy.ndimage import distance_transform_edt,map_coordinates,gaussian_filter
from scipy.spatial import cKDTree
from skimage.measure import marching_cubes,find_contours
R=Path(__file__).resolve().parent;WORK=R.parents[1]
R.mkdir(exist_ok=True)
for variant in ['01','02']:
    source=WORK/f'brand-fire-{variant}.npz';d=np.load(source);mask=d['supply']>.5
    nearest=distance_transform_edt(~mask,return_distances=False,return_indices=True)
    arrival=d['arrival'][tuple(nearest)]/1.875
    sdf=gaussian_filter((distance_transform_edt(mask)-distance_transform_edt(~mask))*.0205,.6)
    yy=np.linspace(-.24,.24,28)
    volume=sdf[:,None,:]-yy[None,:,None]**2/.105
    v,f,_,_=marching_cubes(volume.astype('f4'),0,spacing=(5.8/319,.48/27,10.5/511))
    v=v[:,[2,1,0]];v[:,0]-=5.25;v[:,1]-=.24
    born=map_coordinates(arrival,[v[:,2]/5.8*319,(v[:,0]+5.25)/10.5*511],order=1,mode='nearest')
    rng=np.random.default_rng(722+int(variant));inside=np.argwhere(mask)
    seeds=inside[rng.choice(len(inside),240,replace=False)]
    seeds=np.c_[seeds[:,1]/511*10.5-5.25,seeds[:,0]/319*5.8]
    groups=cKDTree(seeds).query(v[:,[0,2]])[1]
    centers=np.c_[seeds[:,0],np.zeros(len(seeds)),seeds[:,1]]
    paths=[];pathbirth=[]
    for contour in find_contours(mask.astype(float),.5):
        if len(contour)<8:continue
        contour=contour[::2];p=np.c_[contour[:,1]/511*10.5-5.25,np.zeros(len(contour)),contour[:,0]/319*5.8]
        paths.append(p);pathbirth.append(map_coordinates(arrival,[contour[:,0],contour[:,1]],order=1,mode='nearest'))
    counts=np.array([len(p) for p in paths]);offsets=np.r_[0,np.cumsum(counts)]
    n=90000;cells=inside[rng.integers(0,len(inside),n)];zz=(cells[:,0]+rng.uniform(-.45,.45,n))/319*5.8;xx=(cells[:,1]+rng.uniform(-.45,.45,n))/511*10.5-5.25
    depth=np.sqrt(np.maximum(sdf[tuple(cells.T)],.001)*.105)*rng.uniform(-.95,.95,n)
    pp=np.c_[xx,depth,zz];pb=arrival[tuple(cells.T)]
    np.savez_compressed(R/f'source-{variant}.npz',v=v.astype('f4'),faces=f.astype('i4'),born=born.astype('f4'),groups=groups,centers=centers.astype('f4'),particles=pp.astype('f4'),particlebirth=pb.astype('f4'),paths=np.concatenate(paths).astype('f4'),pathbirth=np.concatenate(pathbirth).astype('f4'),offsets=offsets,arrival=arrival.astype('f4'),sdf=sdf.astype('f4'),mask=mask,times=d['times']/1.875,points=d['points'],emit=d['emit'])
    (R/f'source-{variant}.json').write_text(json.dumps({'source':str(source),'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'vertices':len(v),'faces':len(f),'particles':n,'contours':len(paths),'writingSeconds':6.827,'closeSupplyAt':11,'duration':15},indent=2),encoding='utf-8')
    print(variant,len(v),'vertices',len(paths),'contours')
