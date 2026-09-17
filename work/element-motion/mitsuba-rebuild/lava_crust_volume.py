"""CPU separated basalt crust over the existing lava mass.

This replaces the inherited stretched-coordinate relief. The coarse shape
is retained; surface fracture layout is authored, not a fracture solver.
"""
from pathlib import Path
import os,time,json,hashlib,argparse
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='2')
import numpy as np
from scipy.sparse import coo_matrix,diags
from scipy.spatial import cKDTree
from lava_skin import normals
from lava_breakout_cpu import noise,smooth,film_columns
from lava_cohesive_cpu import clip_vents
from lava_lobes_cpu import closed_skin,preview
R=Path(__file__).resolve().parent/'lava-focus';O=R/'crust-volume';O.mkdir(exist_ok=True)

def volume(v,f):return float(np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))/6)

def main(name,rounds):
    start=time.time();source=R/'breakout/basalt-depth-01.npz';a=np.load(source);v=a['v'].astype('f8');f=a['f'];old=v.copy();target=volume(v,f)
    e=np.r_[f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]];adj=coo_matrix((np.ones(len(e)*2),(np.r_[e[:,0],e[:,1]],np.r_[e[:,1],e[:,0]])),shape=(len(v),len(v))).tocsr();avg=diags(1/np.maximum(np.asarray(adj.sum(1)).ravel(),1))@adj
    # Low-pass the folded support mesh. Surface features are then built in
    # metre-scale coordinates instead of the distorted material map.
    for _ in range(rounds):v=.40*v+.60*(avg@v)
    center=v.mean(0);v=center+(v-center)*(target/volume(v,f))**(1/3)
    base=v.copy();n=normals(base,f);rng=np.random.default_rng(8271)
    select=np.flatnonzero(n[:,2]>-.10);rng.shuffle(select);seeds=[];sizes=[]
    for idx in select[::3]:
        size=float(np.clip(.022*(1+rng.pareto(1.7)),.022,.11))
        if seeds and np.min(np.linalg.norm(np.asarray(seeds)-base[idx],axis=1)-np.asarray(sizes)*.70)<size*.70:continue
        seeds.append(base[idx]);sizes.append(size)
        if len(seeds)==440:break
    seeds=np.array(seeds);sizes=np.array(sizes)
    # Power distances create unequal cells. Only selected, strained
    # interfaces open; most of the solid surface stays connected.
    warped=base.copy();warped+=np.c_[noise(base,14,194),noise(base,14,472),noise(base,14,995)]*.004
    d,ix=cKDTree(seeds).query(warped,k=6);power=d-sizes[ix]*.18;order=np.argsort(power,axis=1)
    one=order[:,0];two=order[:,1];row=np.arange(len(base));cell=ix[row,one]
    gap=(power[row,two]-power[row,one])*.5
    active=.12+1.05*smooth(noise(base,5,548)*.8+.30)
    width=.0025+.0045*smooth(noise(base,12,940)+.20)
    opening=smooth(1-gap/width)*active
    upper=smooth((n[:,2]+.25)/.65);opening*=upper
    # A few broader ruptures, with contours perturbed at rock scale.
    for cx,cy,sx,sy in [(-.38,-.08,.115,.035),(.16,-.065,.075,.036),(.025,.21,.086,.027)]:
        q=((base[:,0]-cx)/sx)**2+((base[:,1]-cy)/sy)**2
        tear=smooth((1.1-q-.18*noise(base,24,732))/.50)*upper
        opening=np.maximum(opening,tear*.88)
    lift=.007+.006*smooth(gap/.025)
    rough=.0020*noise(base,42,212)+.00065*noise(base,130,437)
    top=base+n*(lift+rough)[:,None]
    sv,sr,sf=clip_vents(top,base,f,opening,.46)
    used,remap=np.unique(sf,return_inverse=True);sv=sv[used];sr=sr[used];sf=remap.reshape(-1,3)
    thickness=.004+.003*smooth(noise(sr,9,210)+.4)
    st=990+60*smooth(noise(sr,9,810)+.3)
    sv,sf,sn,sr,st=closed_skin(sv,sf,sr,thickness,st)
    # The liquid is independently smooth under the apertures. This gives
    # real banks, occlusion and thickness, rather than glowing pit walls.
    core=base-n*.004
    age=.09+1.5*smooth(noise(base,8,976)+.35)
    grid=np.geomspace(.02,25,100);temps,residual=film_columns(grid)
    ct=np.interp(age,grid,temps);ct=np.where(n[:,2]<-.15,950,ct)
    b=dict(v=np.r_[core,sv].astype('f4'),f=np.r_[f,sf+len(core)].astype('i4'),normal=np.r_[normals(core,f),sn].astype('f4'),rest=np.r_[base,sr].astype('f4'),temperature=np.r_[ct,st].astype('f4'),component=np.r_[np.zeros(len(core),'u1'),np.ones(len(sv),'u1')],camera_eye=a['camera_eye'],camera_target=a['camera_target'],camera_fov=a['camera_fov'])
    b['uv']=b['rest'][:,:2]*4
    path=O/f'{name}.npz';np.savez_compressed(path,**b);preview(b,O/f'{name}-geometry.png')
    area=np.linalg.norm(np.cross(base[f[:,1]]-base[f[:,0]],base[f[:,2]]-base[f[:,0]]),axis=1)
    report={'device':'CPU','source':str(source),'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'meshSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'vertices':len(b['v']),'triangles':len(b['f']),'coarseVolumeRelativeError':abs(volume(base,f)/target-1),'exposedAreaFraction':float(np.sum(area*(opening[f].mean(1)>.46))/area.sum()),'columnEnergyResidual':float(residual),'surfaceSeeds':len(seeds),'smoothIterations':rounds,'seconds':round(time.time()-start,2),'limits':['Authored fracture layout and retained coarse volume; no new fracture or flow solver','Natural 1D cooling only; not a globally coupled energy solve','No motion validation']}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='crust-01');p.add_argument('--rounds',type=int,default=120);args=p.parse_args();main(args.name,args.rounds)
