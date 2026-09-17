"""Solid fitted basalt blocks over the retained lava mass, built on CPU."""
from pathlib import Path
import os,time,json,hashlib,argparse
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='2')
import numpy as np
from scipy.spatial import cKDTree
from lava_skin import normals
from lava_breakout_cpu import noise,smooth,film_columns
from lava_cohesive_cpu import clip_vents
from lava_lobes_cpu import closed_skin,preview
R=Path(__file__).resolve().parent/'lava-focus';O=R/'crust-volume'

def main(name):
    start=time.time();source=O/'crust-01.npz';a=np.load(source);mask=a['component']==0;base=a['rest'][mask].astype('f8');f=a['f'][mask[a['f']].all(1)];n=normals(base,f);rng=np.random.default_rng(14568)
    candidates=np.flatnonzero(n[:,2]>-.25);rng.shuffle(candidates);seeds=[];radii=[]
    for idx in candidates[::6]:
        radius=float(np.clip(.040*(1+rng.pareto(1.45)),.040,.16))
        if seeds and np.any(np.linalg.norm(np.array(seeds)-base[idx],axis=1)<.63*(np.array(radii)+radius)):continue
        seeds.append(base[idx]);radii.append(radius)
        if len(seeds)==185:break
    seeds=np.array(seeds);radii=np.array(radii)
    warp=base+np.c_[noise(base,9,923),noise(base,9,231),noise(base,9,652)]*.013
    warp+=np.c_[noise(base,31,112),noise(base,31,913),noise(base,31,828)]*.003
    d,ix=cKDTree(seeds).query(warp,k=8);power=d-radii[ix]*.50;order=np.argsort(power,axis=1);row=np.arange(len(base));one=order[:,0];two=order[:,1];cell=ix[row,one];best=power[row,one];second=power[row,two]
    core=base-n*.012;age=.025+.32*smooth(noise(base,11,333)+.40);grid=np.geomspace(.01,15,90);temps,residual=film_columns(grid);ct=np.interp(age,grid,temps);ct=np.where(n[:,2]<-.16,950,ct)
    verts=[core];faces=[f];norm=[normals(core,f)];rest=[base];temperature=[ct];component=[np.zeros(len(core),'u1')];offset=len(core);blocks=[]
    width=.0012+.0027*smooth(noise(base,6,421)+.30)
    rough=.0055*noise(base,27,367)+.0014*noise(base,96,193)
    # Every fragment occupies its own part of the parent crust. They are
    # packed by construction, rather than scattered onto a liquid sheet.
    for ci in range(len(seeds)):
        chosen=np.any(cell[f]==ci,axis=1)
        if not chosen.any():continue
        ids,inv=np.unique(f[chosen],return_inverse=True);tri=inv.reshape(-1,3);p=base[ids]
        own=np.linalg.norm(warp[ids]-seeds[ci],axis=1)-radii[ci]*.50
        other=np.where(cell[ids]==ci,second[ids],best[ids]);side=own-other+width[ids]
        axis=n[ids].mean(0);axis/=np.linalg.norm(axis)
        top=p+n[ids]*(.009+rough[ids])[:,None]
        sv,sr,sf=clip_vents(top,p,tri,side,0.)
        if not len(sf):continue
        used,remap=np.unique(sf,return_inverse=True);sv=sv[used];sr=sr[used];sf=remap.reshape(-1,3)
        if len(sv)<6:continue
        pivot=sv.mean(0);tilt=rng.normal(size=3);tilt-=axis*(tilt@axis);tilt/=np.linalg.norm(tilt);angle=float(rng.uniform(-.12,.12))
        delta=sv-pivot;sv=pivot+delta*np.cos(angle)+np.cross(tilt,delta)*np.sin(angle)+tilt[None,:]*(delta@tilt)[:,None]*(1-np.cos(angle))
        lift=.004+.018*float(smooth(noise(seeds[ci:ci+1],7,856)+.35)[0]);sv+=axis*lift
        thickness=np.full(len(sv),.023+radii[ci]*.25)
        st=np.full(len(sv),float(rng.uniform(925,1040)))
        sv,sf,sn,sr,st=closed_skin(sv,sf,sr,thickness,st)
        verts.append(sv);faces.append(sf+offset);norm.append(sn);rest.append(sr);temperature.append(st);component.append(np.ones(len(sv),'u1'));offset+=len(sv)
        blocks.append({'radiusM':float(radii[ci]),'thicknessM':float(thickness[0]),'tiltRad':angle,'liftM':lift})
    b=dict(v=np.concatenate(verts).astype('f4'),f=np.concatenate(faces).astype('i4'),normal=np.concatenate(norm).astype('f4'),rest=np.concatenate(rest).astype('f4'),temperature=np.concatenate(temperature).astype('f4'),component=np.concatenate(component),camera_eye=a['camera_eye'],camera_target=a['camera_target'],camera_fov=a['camera_fov']);b['uv']=b['rest'][:,:2]*4
    path=O/f'{name}.npz';np.savez_compressed(path,**b);preview(b,O/f'{name}-geometry.png')
    report={'device':'CPU','sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'meshSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'vertices':len(b['v']),'triangles':len(b['f']),'blocks':len(blocks),'thicknessRangeM':[min(q['thicknessM'] for q in blocks),max(q['thicknessM'] for q in blocks)],'columnEnergyResidual':float(residual),'seconds':round(time.time()-start,2),'limits':['Authored packed fracture blocks; not a rigid-body or fracture solve','Tilt and lift are authored, and block interpenetration has not been ruled out','Local cooling only, not coupled thermal-fluid dynamics']}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='blocks-01');a=p.parse_args();main(a.name)
