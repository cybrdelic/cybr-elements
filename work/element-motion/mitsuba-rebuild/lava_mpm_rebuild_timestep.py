"""Three timestep CPU tensile tests; no historic cache or authored damage."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import argparse,json,time
import numpy as np
from lava_mpm import MPM,Material,ROOT,block
from lava_mpm_loading import extension_grips
from lava_mpm_coupled import advance


def run(temperature,dt,duration,adaptive,refinement=1,wall=120):
    sample=np.array([.001,.0005,.0005])/refinement;cell=sample*2
    x=block([-.004,-.001,.001],[.004,.001,.003],sample)
    m=Material(fracture_length=.005)
    shape=np.array([10,8,9])*refinement+1
    s=MPM(x,sample[0],cell[0],temperature=temperature,material=m,cell_size=cell,sample_size=sample,ground=False,gravity=(0,0,0),origin=[-.01,-.004,-.002],shape=shape)
    speed=.0001
    def grips(xyz):
        mask=np.zeros_like(xyz,dtype=bool);value=np.zeros_like(xyz)
        mask[:,0]=abs(xyz[:,0])>=.0035;value[:,0]=np.sign(xyz[:,0])*speed
        return mask,value
    start=time.time();report={}
    failure=None
    try:
        if adaptive:report=advance(s,duration,max_dt=dt,max_trials=200,thermal=False,node_velocity=grips)
        else:
            while s.time<duration-1e-12:
                s.step(min(dt,duration-s.time),thermal=False,node_velocity=grips)
                if time.time()-start>wall:raise RuntimeError('CPU wall budget reached; last accepted state retained')
    except Exception as exc:failure=str(exc)
    name=f'tension-{temperature:g}-{dt:g}'+('-adaptive' if adaptive else '')
    if duration!=.02:name+=f'-duration{duration:g}'
    if refinement!=1:name+=f'-refine{refinement}'
    folder=ROOT/'rebuild-24'/name;s.save(folder)
    result=dict(name=name,complete=failure is None,failure=failure,temperatureK=temperature,dt=dt,duration=s.time,requestedDuration=duration,refinement=refinement,particles=len(x),maximumDamage=float(s.damage.max()),meanDamage=float(s.damage.mean()),speed=float(np.linalg.norm(s.v,axis=1).max()),boundaryWorkJ=s.ledger.get('prescribed_boundary_work',0.),wallSeconds=time.time()-start,adaptive=report,limits='Small laboratory tensile test; no cooling or free-flow claim.')
    (folder/'proof.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='adaptive'}),flush=True)
    return s,result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--temperature',type=float,default=850.);p.add_argument('--dt',type=float,default=.002);p.add_argument('--duration',type=float,default=.02);p.add_argument('--adaptive',action='store_true');p.add_argument('--refinement',type=int,default=1);a=p.parse_args();run(a.temperature,a.dt,a.duration,a.adaptive,a.refinement)
