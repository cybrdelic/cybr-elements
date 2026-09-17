"""Full-opening MPM screening test with a geometric edge notch.

A machined notch localizes fracture. There is no initial damage or broken
connectivity. Displacement-controlled grips are declared laboratory loads.
"""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import argparse,json,time
import numpy as np
from lava_mpm import ROOT,MPM,Material,block,SOURCE_HASHES

def run(dt,refine,wall,duration=.12,resume=False):
    sample=np.array([.001,.0005,.0005])/refine;cell=2*sample
    x=block([-.010,-.001,.001],[.010,.001,.002],sample)
    x=x[~((abs(x[:,0])<.001)&(x[:,1]>0))]
    s=MPM(x,sample[0],cell[0],temperature=850.,material=Material(fracture_length=.002),ground=False,gravity=(0,0,0),cell_size=cell,sample_size=sample,origin=[-.016,-.004,-.002],shape=np.array([18,9,9])*refine+1)
    folder=ROOT/'rebuild-25'/f'notch-{dt:g}-r{refine}';folder.mkdir(parents=True,exist_ok=True)
    old_proof={}
    if resume:
        meta=json.loads((folder/'state.json').read_text())
        if meta['sourceHashes']!=SOURCE_HASHES:raise ValueError('Resume requires identical solver source')
        s=MPM.load(folder);old_proof=json.loads((folder/'proof.json').read_text())
    (folder/'setup.json').write_text(json.dumps(dict(sceneKind='notched_tensile_specimen',lengthM=.020,crossSectionM=[.002,.001],notch='2 mm long, 1 mm deep geometric side notch at the centre',fractureLengthM=.002,gripSpeedMPerS=.001,initialDamage=0,initialBrokenEdges=0,sourceHashes=SOURCE_HASHES),indent=2))
    def grips(xyz):
        end=abs(xyz[:,0])>=.009;value=np.zeros_like(xyz);value[:,0]=np.sign(xyz[:,0])*.001
        return np.broadcast_to(end[:,None],xyz.shape).copy(),value
    start=time.time();error=None;rejections=old_proof.get('rejections',0);step=dt;count=len(s.rows);first_break=old_proof.get('firstBreakTime')
    try:
        while s.time<duration-1e-12:
            try:
                s._solve_deadline=time.monotonic()+max(0,wall-(time.time()-start))
                row=s.step(min(step,duration-s.time),thermal=False,node_velocity=grips)
            except RuntimeError:
                rejections+=1;step*=.5
                if step<1e-8:raise
                if time.time()-start>wall:raise RuntimeError('CPU screening budget exhausted during rejected step')
                continue
            count+=1
            if s.connectivity.broken.any() and first_break is None:
                first_break=s.time;s.save(folder/'first-break')
            if count%20==0:
                print(json.dumps(dict(time=s.time,damage=float(s.damage.max()),broken=int(s.connectivity.broken.sum()),step=step,wallSeconds=time.time()-start)),flush=True)
            step=min(dt,step*1.5)
            if time.time()-start>wall:raise RuntimeError('CPU screening budget exhausted')
    except Exception as exc:error=str(exc)
    s.save(folder)
    components=len(np.unique(s.connectivity.labels[s.connectivity.frozen]))
    separated=not np.intersect1d(s.connectivity.labels[s.rest[:,0]<-.008],s.connectivity.labels[s.rest[:,0]>.008]).size
    result=dict(status='pass' if error is None else 'incomplete',error=error,time=s.time,oppositeGripsDisconnected=separated,firstBreakTime=first_break,brokenEdges=int(s.connectivity.broken.sum()),components=components,maximumDamage=float(s.damage.max()),workJ=s.ledger.get('prescribed_boundary_work',0),maxSpeed=float(np.linalg.norm(s.v,axis=1).max()),steps=count,rejections=rejections,dt=dt,refinement=refine,wallSeconds=time.time()-start,sourceHashes=SOURCE_HASHES,
        limits='Full-opening screen; timestep and spatial comparisons must be evaluated separately. Laboratory loading, not natural lava.')
    (folder/'proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dt',type=float,default=.002);p.add_argument('--refine',type=int,default=1);p.add_argument('--wall',type=float,default=120);p.add_argument('--duration',type=float,default=.12);p.add_argument('--resume',action='store_true');a=p.parse_args();run(a.dt,a.refine,a.wall,a.duration,a.resume)
