"""Conductive preparation / fresh-face cooling for cached basalt geometry.

This repairs the optical initial condition. It is NOT a rerun of the MPM
constitutive solve and does not claim coupled rock/melt heat exchange.
"""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
from pathlib import Path
import numpy as np,json
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation
from scipy.sparse import diags
from lava_relief36 import relief,render,radiance
from lava_mpm import Material,heat_solve


def column(initial,age,depth=.04,count=160,dt=1.):
    m=Material();dz=depth/count;z=(np.arange(count)+.5)*dz
    mass=np.full(count,m.density*dz);h=m.enthalpy(np.full(count,initial));start=mass@h
    k=m.conductivity/dz;diag=np.full(count,2*k);diag[[0,-1]]=k
    K=diags([-np.full(count-1,k),diag,-np.full(count-1,k)],[-1,0,1]).tocsr()
    top=np.zeros(count);top[0]=1;bottom=np.zeros(count);bottom[-1]=1
    lost=0.;clock=0.
    while clock<age-1e-9:
        step=min(dt,age-clock);h,row=heat_solve(m,h,mass,K,top,np.full(count,m.ambient),step,bottom,2*k,initial)
        lost+=float(np.sum(row['radiation']+row['convection']+row['bed']));clock+=step
    return z,m.temperature(h),abs(float(mass@h-start+lost))/max(abs(float(start)),1.)


def rebuild(source,preparation=90.):
    folder=source.parent/(source.stem+'-relief36');mesh=folder/'surface.ply'
    with mesh.open('rb') as f:
        count=0
        while True:
            line=f.readline()
            if line.startswith(b'element vertex'):count=int(line.split()[-1])
            if line==b'end_header\n':offset=f.tell();break
    names=['x','y','z','nx','ny','nz','heat_r','heat_g','heat_b','solid_0']
    a=np.memmap(mesh,dtype=[(k,'<f4') for k in names],mode='r+',offset=offset,shape=(count,))
    first=int(np.flatnonzero(a['solid_0']==1)[0]);color=np.stack([a['heat_'+c] for c in 'rgb'],axis=1)
    s=np.load(source);rocks=np.load(source.parent/'rocks.npz');age=float(s['time'])
    # A load-bearing crystal-rich core, not a 1450 K fully molten rigid body.
    z,profile,error=column(1250.,preparation)
    bulk=np.arange(500.,1261.,10.);cooled=[];errors=[error]
    for t in bulk:
        _,ts,e=column(t,age,depth=.004,count=80,dt=.04);cooled.append(ts[0]);errors.append(e)
    table_t=np.arange(450.,1452.);table=np.array([radiance(t) for t in table_t])*.94
    start=first;maxPositionError=0.;tempRanges=[]
    for i,q in enumerate(s['body_q']):
        original=rocks[f'v{i}'];v,f=relief(original,rocks[f'f{i}'],36000+i);end=start+len(v)
        world=v@Rotation.from_quat(q[3:]).as_matrix().T+q[:3]
        saved=np.stack([a[c][start:end] for c in 'xyz'],axis=1)
        err=float(np.max(abs(world-saved)));maxPositionError=max(maxPositionError,err)
        if err>2e-7:raise ValueError('Material point order differs from saved geometry')
        hull=ConvexHull(original);roof=hull.equations[hull.equations[:,2]>.3]
        top=np.full(len(v),1e3)
        for plane in roof:top=np.minimum(top,-(v[:,:2]@plane[:2]+plane[3])/plane[2])
        initial=np.interp(np.maximum(top-v[:,2],0),z,profile)
        if 'base_temperature' in rocks and rocks['base_temperature'][i]<1000:initial=np.minimum(initial,rocks['base_temperature'][i])
        temperature=np.interp(initial,bulk,cooled)
        color[start:end]=np.stack([np.interp(temperature,table_t,table[:,j]) for j in range(3)],axis=-1)
        tempRanges.append([float(temperature.min()),float(temperature.max())]);start=end
    if start!=count:raise ValueError('Unassigned mesh vertices')
    for j,c in enumerate('rgb'):a['heat_'+c]=color[:,j]
    a.flush();del a
    out=folder/f'thermal37-{preparation:g}';out.mkdir(exist_ok=True)
    receipt=dict(method='1D finite-volume enthalpy with latent heat, radiation, convection and a metered bottom reservoir. Conductive crust preparation; exposed fracture-face cooling for cache time.',coreK=1250,preparationSeconds=preparation,maximumColumnRelativeEnergyError=max(errors),maximumGeometryCorrespondenceErrorM=maxPositionError,temperatureRangesK=tempRanges,source=str(source),limitations='Initial fragments and preparation age remain authored. The optical temperature revision is not fed back into the cached MPM / rigid dynamics, and is not a full coupled lava result.')
    (out/'thermal.json').write_text(json.dumps(receipt,indent=2));print(json.dumps({k:v for k,v in receipt.items() if k!='temperatureRangesK'}),flush=True)
    return mesh,out


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--preparation',type=float,default=90);p.add_argument('--width',type=int,default=800);p.add_argument('--spp',type=int,default=48);a=p.parse_args()
    mesh,out=rebuild(a.source,a.preparation);render(mesh,out,a.width,a.spp)
