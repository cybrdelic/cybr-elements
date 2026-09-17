from pathlib import Path
import numpy as np,cv2,json
from scipy.ndimage import distance_transform_edt,gaussian_filter,map_coordinates
from scipy.spatial import cKDTree
from skimage.measure import marching_cubes
root=Path(__file__).parent
for variant in ['01','02']:
    data=np.load(root/f'brand-fire-{variant}.npz');m=data['supply'];arrival=data['arrival']
    sdf=gaussian_filter((distance_transform_edt(m)-distance_transform_edt(1-m))*.0205,.7)
    depth=np.linspace(-.33,.33,40)
    field=sdf[:,None,:]-depth[None,:,None]**2/.15
    v,f,n,_=marching_cubes(field.astype('float32'),0,spacing=(5.8/319,.66/39,10.5/511))
    v=v[:,[2,1,0]];v[:,0]-=5.25;v[:,1]-=.33
    # Each fragment has shared vertices internally, independent boundaries.
    rng=np.random.default_rng(510+int(variant));inside=np.argwhere(m>.5)
    seeds=inside[rng.choice(len(inside),420,replace=False)]
    seeds=np.c_[seeds[:,1]/511*10.5-5.25,seeds[:,0]/319*5.8]
    fc=v[f].mean(1);groups=cKDTree(seeds).query(fc[:,[0,2]])[1]
    keys=(groups[:,None]*len(v)+f).ravel();uniq,inv=np.unique(keys,return_inverse=True)
    ids=uniq//len(v);verts=v[uniq%len(v)];faces=inv.reshape(-1,3)
    centers=np.zeros((420,3));np.add.at(centers,ids,verts);counts=np.bincount(ids,minlength=420);centers/=np.maximum(counts[:,None],1)
    nearest=distance_transform_edt(1-m,return_distances=False,return_indices=True);arr=arrival[tuple(nearest)]
    born=map_coordinates(arr,[verts[:,2]/5.8*319,(verts[:,0]+5.25)/10.5*511],order=1,mode='nearest')/1.875
    groupbirth=map_coordinates(arr,[centers[:,2]/5.8*319,(centers[:,0]+5.25)/10.5*511],order=1,mode='nearest')/1.875
    np.savez_compressed(root/f'element-mark-{variant}.npz',verts=verts.astype('f'),faces=faces.astype('i'),groups=ids.astype('i'),centers=centers.astype('f'),born=born.astype('f'),groupbirth=groupbirth.astype('f'))
    cv2.imwrite(str(root/f'element-mask-{variant}.png'),np.flipud((gaussian_filter(m,1.7)*65535).astype('uint16')))
    cv2.imwrite(str(root/f'element-arrival-{variant}.png'),np.flipud((np.minimum(arrival,32)/32*65535).astype('uint16')))
    print(json.dumps({'variant':variant,'surfaceVertices':len(verts),'triangles':len(faces),'fragments':420}))
