"""Continue the failed softening test using measured temporal error control."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import argparse,json,time
import numpy as np
from lava_mpm import ROOT,MPM
from lava_mpm_coupled import advance


def main(source_name,duration,name,transfer,filter_seconds=None,wall=100):
    source=ROOT/'rebuild-24'/source_name;s=MPM.load(source);initial=s.time;start=time.time()
    if transfer is not None:s.transfer=transfer
    if filter_seconds is not None:s.transfer_filter_seconds=filter_seconds
    def grips(xyz):
        mask=np.zeros_like(xyz,dtype=bool);value=np.zeros_like(xyz)
        mask[:,0]=abs(xyz[:,0])>=.0035;value[:,0]=np.sign(xyz[:,0])*.0001
        return mask,value
    report={};error=None
    try:report=advance(s,duration,max_dt=.0005,max_trials=800,max_wall=wall,thermal=False,node_velocity=grips)
    except Exception as exc:error=str(exc);report=getattr(s,'_adaptive_report',{})
    folder=ROOT/'rebuild-24'/name;s.save(folder)
    result=dict(status='pass' if error is None else 'fail',error=error,startTime=initial,endTime=s.time,requestedEndTime=initial+duration,
        maximumDamage=float(s.damage.max()),meanDamage=float(s.damage.mean()),maximumFCondition=float(np.linalg.cond(s.F).max()),
        boundaryWorkJ=s.ledger.get('prescribed_boundary_work',0),brokenEdges=int(s.connectivity.broken.sum()),transfer=s.transfer,transferFilterSeconds=s.transfer_filter_seconds,adaptive=report,wallSeconds=time.time()-start,
        limit='Local-error-controlled continuation of the failed tensile specimen, not an independent refinement comparison.')
    (folder/'proof.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='adaptive'}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',default='tension-850-0.002-duration0.1');p.add_argument('--duration',type=float,default=.01);p.add_argument('--name',default='softening-recovery');p.add_argument('--transfer',choices=['apic','impulse_affine']);p.add_argument('--filter-seconds',type=float);p.add_argument('--wall',type=float,default=100);a=p.parse_args();main(a.source,a.duration,a.name,a.transfer,a.filter_seconds,a.wall)
