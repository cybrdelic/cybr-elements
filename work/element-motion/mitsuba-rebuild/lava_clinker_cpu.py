"""CPU clinkery lava study: connected melt carrying authored basalt rubble.

The original granular direction is retained as actual solid fragments. This
is an authored snapshot, not a solved rigid-body/fluid coupling.
"""
import os,time,json,hashlib
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='2')
from pathlib import Path
import numpy as np
import trimesh
from scipy.spatial import cKDTree,ConvexHull
from lava_breakout_cpu import core_mesh,noise,smooth,film_columns
from lava_skin import normals
from lava_lobes_cpu import preview

R=Path(__file__).resolve().parent/'lava-focus';O=R/'breakout'

def rock(center,normal,size,seed):
    rng=np.random.default_rng(seed)
    q=rng.normal(size=(24,3));q/=np.linalg.norm(q,axis=1)[:,None];q*=rng.uniform(.72,1.10,(len(q),1))
    hull=ConvexHull(q);f=hull.simplices
    wrong=np.sum(np.cross(q[f[:,1]]-q[f[:,0]],q[f[:,2]]-q[f[:,0]])*q[f].mean(1),axis=1)<0
    f[wrong]=f[wrong][:,[0,2,1]]
    mesh=trimesh.Trimesh(q,f,process=True)
    for _ in range(3):mesh=mesh.subdivide()
    v=np.array(mesh.vertices);f=np.array(mesh.faces);n=normals(v,f)
    # Small open vesicles and broken surface relief, subordinate to the
    # large angular shape. These are real depressions in the geometry.
    pore=rng.normal(size=(50,3));pore/=np.linalg.norm(pore,axis=1)[:,None];pore*=rng.uniform(.75,1.05,(50,1))
    d,_=cKDTree(pore).query(v,k=1)
    pits=-.045*np.exp(-(d/.077)**2)
    v+=n*(.024*noise(v,12,seed+11)+pits)[:,None]
    axis=np.array([0.,0.,1.]);side=np.cross(axis,normal)
    if np.linalg.norm(side)<1e-6:side=np.array([1.,0.,0.])
    side/=np.linalg.norm(side);up=np.cross(normal,side)
    angle=rng.uniform(-np.pi,np.pi);xx=np.cos(angle)*side+np.sin(angle)*up;yy=-np.sin(angle)*side+np.cos(angle)*up
    basis=np.array([xx,yy,normal]);scale=np.array([size*rng.uniform(.85,1.25),size*rng.uniform(.65,.90),size*rng.uniform(.40,.63)])
    rest=v.copy();v=(v*scale)@basis+center
    return v,f,normals(v,f),rest

def main():
    start=time.time();v,f,n,r=core_mesh(.0032);rng=np.random.default_rng(385)
    # Fragments lie on the convex flow, with the source near the back and
    # progressively cooler skin toward the leading toes.
    upper=(n[:,2]>-.15)&(r[:,2]>-.025);candidates=np.flatnonzero(upper)
    rng.shuffle(candidates);centers=[];sizes=[];directions=[]
    accepted=[]
    for idx in candidates[::7]:
        size=float(np.clip(.017*(1+rng.pareto(1.7)),.016,.100))
        x,y,z=r[idx]
        # Keep one irregular active channel through the rubble, not a
        # uniform glowing ring around a flat crust slab.
        channel=np.exp(-((y+.05+.065*np.sin(7*x))/.044)**2)*smooth((x+.15)/.18)*smooth((.53-x)/.10)
        if rng.random()<channel*.80:continue
        if centers:
            dist=np.linalg.norm(np.asarray(centers)-v[idx],axis=1)
            if np.any(dist<(.79*(np.asarray(sizes)+size))):continue
        centers.append(v[idx]+n[idx]*size*.20);sizes.append(size);directions.append(n[idx]);accepted.append(idx)
        if len(centers)>=360:break
    # Cool the exposed banks next to the rock/melt contacts continuously.
    tree=cKDTree(np.asarray(centers));dist,near=tree.query(v,k=4)
    gap=np.min(dist-np.asarray(sizes)[near]*.75,axis=1)
    age=.10+5*smooth((r[:,0]+.4)/1.1)+.5*smooth(noise(r,27,326)+.4)
    age+=22*(1-smooth((gap+.005)/.025))
    age+=35*smooth((r[:,0]-.53)/.10)
    grid=np.geomspace(.01,100,120);temp,residual=film_columns(grid)
    ct=np.interp(age,grid,temp);ct=np.where(n[:,2]<-.16,950,ct)
    pieces=[(v,f,n,r,ct,np.zeros(len(v),'u1'))];offset=len(v)
    for i,(c,d,s) in enumerate(zip(centers,directions,sizes)):
        rv,rf,rn,rr=rock(c,d,s,730+i*113)
        # Fractured undersides remain warmer, tops are quenched basalt.
        local=(rv-c)@d
        rt=940+200*smooth((-local/s+.25)/.8)+42*smooth(noise(rv,50,323)+.4)
        pieces.append((rv,rf+offset,rn,rv.copy(),rt,np.ones(len(rv),'u1')));offset+=len(rv)
    fields=list(zip(*pieces))
    a=dict(v=np.concatenate(fields[0]).astype('f4'),f=np.concatenate(fields[1]).astype('i4'),normal=np.concatenate(fields[2]).astype('f4'),rest=np.concatenate(fields[3]).astype('f4'),temperature=np.concatenate(fields[4]).astype('f4'),component=np.concatenate(fields[5]),camera_eye=np.array([1.18,-2.10,1.48]),camera_target=np.array([-.03,.02,.10]),camera_fov=np.array(32.))
    a['uv']=a['rest'][:,:2]*4
    path=O/'clinker-01.npz';np.savez_compressed(path,**a);preview(a,O/'clinker-01-geometry.png')
    report={'device':'CPU','sourceSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'vertices':len(a['v']),'triangles':len(a['f']),'fragments':len(centers),'fragmentRadiusRangeM':[min(sizes),max(sizes)],'columnEnergyResidual':float(residual),'seconds':round(time.time()-start,2),'method':'Connected melt and solid irregular vesicular basalt fragments with real underfaces; temperature-dependent optical surfaces','limits':['Rubble placement, contact cooling age and temperatures are authored; there is no two-way mechanics or rigid-body collision solve','The natural cooling column is solved in 1D only','Still material study; motion is not validated']}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':main()
