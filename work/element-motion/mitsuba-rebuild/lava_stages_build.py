"""Matched lava lifecycle material stills. CPU geometry, not a time-lapse claim."""
from pathlib import Path
import os,json,time,sys
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import ConvexHull
from scipy.ndimage import gaussian_filter
from skimage.measure import marching_cubes
from lava_skin import normals
from lava_breakout_cpu import noise,smooth
R=Path(__file__).resolve().parent/'lava-focus';O=R/'stages';O.mkdir(exist_ok=True)

def compact(a,faces):
    ids,ix=np.unique(faces,return_inverse=True)
    b={k:a[k][ids].copy() for k in ['v','normal','rest','uv','temperature','component']}
    b['f']=ix.reshape(-1,3)
    for k in ['camera_eye','camera_target','camera_fov']:b[k]=a[k]
    return b

def save(name,b):
    b['normal']=normals(b['v'],b['f']).astype('f4')
    partial=O/(name+'.partial.npz');np.savez_compressed(partial,**b);partial.replace(O/(name+'.npz'))

def build_rock_stages():
    start=time.time();a=dict(np.load(R/'crust-volume/blocks-01.npz'));f=a['f'];v=a['v']
    e=np.r_[f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]
    adj=coo_matrix((np.ones(len(e),'u1'),(e[:,0],e[:,1])),shape=(len(v),len(v))).tocsr()
    _,labels=connected_components(adj,directed=False)
    core=a['component']==0;corefaces=f[core[f].all(1)]
    magma=compact(a,corefaces)
    magma['v']+=magma['normal']*(.0015*noise(magma['rest'],35,878))[:,None]
    magma['temperature'][:]=1450-25*smooth(noise(magma['rest'],7,996)+.35)
    save('magma',magma)
    keep=core.copy()
    for label in np.unique(labels[~core]):
        mask=labels==label;p=a['rest'][mask].mean(0)
        # Coherent rafts accumulate on the older, upstream part; no loose dots.
        if p[0]<-.34 or (noise(p[None,:],5,992)[0]>.05 and p[0]<.28):keep[mask]=True
    lava=compact(a,f[keep[f].all(1)])
    c=lava['component']==0
    lava['temperature'][c]=1360+65*smooth(noise(lava['rest'][c],8,197)+.35)
    lava['temperature'][~c]+=110
    save('lava',lava)
    cooling={k:q.copy() for k,q in a.items()};save('cooling',cooling)
    basalt={k:q.copy() for k,q in a.items()};basalt['temperature'][:]=293.15;save('basalt',basalt)

def main():
    start=time.time()
    if '--basalt-only' in sys.argv:
        b=dict(np.load(R/'crust-volume/blocks-01.npz'));b['temperature'][:]=293.15;save('basalt',b);print('Basalt cache repaired atomically');return
    if '--obsidian-only' not in sys.argv:build_rock_stages()
    a=np.load(O/'magma.npz')
    # A separate high-silica glass branch. Convex break planes and concave
    # conchoidal scars are geometry; never a glossy recolor of the basalt mesh.
    rng=np.random.default_rng(6729);p=rng.normal(size=(46,3));p/=np.linalg.norm(p,axis=1)[:,None]
    p*=np.array([.76,.34,.255]);p+=np.array([-.12,0,.235])
    hull=ConvexHull(p);eq=hull.equations
    dx=.010;origin=np.array([-1.0,-.48,-.06]);axes=[np.arange(origin[i],hi,dx) for i,hi in enumerate([.79,.49,.59])]
    grid=np.stack(np.meshgrid(*axes,indexing='ij'),axis=-1);flat=grid.reshape(-1,3)
    field=np.full(len(flat),-1e4)
    for plane in eq:field=np.maximum(field,flat[:,0]*plane[0]+flat[:,1]*plane[1]+flat[:,2]*plane[2]+plane[3])
    for center,radius in [([-.35,-.88,.56],.76),([.22,-.72,.48],.63),([.36,.35,1.07],.71),([-.33,.49,.91],.65),([-.64,-.36,.60],.30)]:
        sphere=np.linalg.norm(flat-center,axis=1)-radius;field=np.maximum(field,-sphere)
    field=gaussian_filter(field.reshape(grid.shape[:-1]),.38)
    ov,of,_,_=marching_cubes(field.astype('f4'),0,spacing=(dx,dx,dx),gradient_direction='ascent');ov+=origin
    if np.sum(ov[of[:,0]]*np.cross(ov[of[:,1]],ov[of[:,2]]))<0:of=of[:,[0,2,1]]
    obs=dict(v=ov.astype('f4'),f=of.astype('i4'),rest=ov.astype('f4'),uv=ov[:,:2].astype('f4')*4,temperature=np.full(len(ov),293.15,'f4'),component=np.zeros(len(ov),'u1'))
    for k in ['camera_eye','camera_target','camera_fov']:obs[k]=a[k]
    save('obsidian',obs)
    report={'device':'CPU','seconds':round(time.time()-start,2),'stages':['magma','lava','cooling','basalt','obsidian'],'states':'Authored matched material states; not a seconds-long crystallization time-lapse','obsidian':'Separate silica-rich composition / quenched glass branch, not basalt transformed into obsidian','geometry':'Magma bare coherent melt; lava with partial crust rafts; cooling and basalt share thick fitted blocks; obsidian has its own fracture geometry','source':'crust-volume/blocks-01.npz'}
    (O/'build.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':main()
