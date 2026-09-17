"""Checkpointed CPU simulation chunks; no render queue."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
from lava_mpm import MPM,Material,ROOT,block


def initial(dx):
    spacing=dx/2
    x=block([-.05,-.035,0],[.05,.035,.03],spacing)
    # An initially molten, shallow elliptical volume. This is an initial
    # condition, with no crust geometry or prescribed fragment motion.
    r=(x[:,0]/.05)**2+(x[:,1]/.035)**2
    top=.025*np.sqrt(np.maximum(0,1-r))
    x=x[(r<1)&(x[:,2]<top)]
    return MPM(x,spacing,dx,temperature=1450.,origin=[-.10,-.08,-.04],shape=[round(.28/dx)+1,round(.16/dx)+1,round(.16/dx)+1],
               gravity=(9.81*np.sin(np.deg2rad(7)),0,-9.81*np.cos(np.deg2rad(7))))


def main(name,seconds,wall,dx,dt,reset,with_gas=False,gas_dx=.01,with_bed=False):
    out=ROOT/name;out.mkdir(parents=True,exist_ok=True)
    if reset and (out/'state.npz').exists():raise ValueError('Use a new run name; existing simulations are preserved')
    s=MPM.load(out) if (out/'state.npz').exists() else initial(dx)
    gas=None
    bed=None
    if with_bed:
        from lava_mpm_bed import Bed
        if (out/'bed.npz').exists():bed=Bed.load(out/'bed.npz')
        else:
            if s.time>0:raise ValueError('A finite bed must start with the material; use a new run name')
            bed=Bed()
    if with_gas:
        from lava_mpm_gas import Gas
        if (out/'gas.npz').exists():gas=Gas.load(out/'gas.npz')
        else:
            if s.time>0:raise ValueError('Gas must begin at the same initial state; use a new run name')
            gas=Gas(origin=(-.10,-.08,0),shape=(round(.28/gas_dx),round(.16/gas_dx),round(.32/gas_dx)),dx=gas_dx);gas.initialize_material(s.x,s.volume)
    history_path=out/'source-history.json';history=json.loads(history_path.read_text()) if history_path.exists() else []
    root=Path(__file__).resolve().parent
    history.append(dict(startPhysicalTime=s.time,sourceHashes={k:hashlib.sha256((root/k).read_bytes()).hexdigest() for k in ('lava_mpm.py','lava_mpm_fracture.py','lava_mpm_gas.py','lava_mpm_bed.py','lava_mpm_run.py')}))
    history_path.write_text(json.dumps(history,indent=2))
    start=time.time();target=s.time+seconds;next_save=s.time;steps=0
    if not (out/'state.npz').exists():
        s.save(out);np.savez_compressed(out/'frame-000000.npz',**dict(np.load(out/'state.npz')))
    while s.time < target-1e-9:
        speed=float(np.linalg.norm(s.v,axis=1).max(initial=0));gradient=float(np.linalg.norm(s.C,axis=(1,2)).max(initial=0))
        actual=min(dt,.18*s.dx/max(speed,.0001),.15/max(gradient,.0001),target-s.time)
        row=s.step(actual,gas=gas,bed=bed);steps+=1
        if gas is not None:row['gas']=gas.advance(actual,s.x,s.volume)
        if bed is not None:row['bed']=bed.advance(actual)
        if s.time>=next_save or time.time()-start>wall:
            s.save(out);frame=out/f'frame-{round(s.time*1000):06}.npz';np.savez_compressed(frame,**dict(np.load(out/'state.npz')))
            if gas is not None:gas.save(out/'gas.npz')
            if bed is not None:bed.save(out/'bed.npz')
            print(json.dumps({k:row[k] for k in ('time','particles','meanSolidFraction','maximumSpeed','damagedParticles','thermalBalanceRelative','seconds')}),flush=True)
            next_save=s.time+max(.5,dt)
        if time.time()-start>wall:break
    s.save(out)
    if gas is not None:gas.save(out/'gas.npz')
    if bed is not None:bed.save(out/'bed.npz')
    result=dict(run=name,physicalSeconds=s.time,chunkSteps=steps,wallSeconds=time.time()-start,completedTarget=s.time>=target-1e-8,
                stateSha256=hashlib.sha256((out/'state.npz').read_bytes()).hexdigest(),device='CPU',latest=s.rows[-1] if s.rows else {})
    (out/'progress.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='coupled-01');p.add_argument('--seconds',type=float,default=1.);p.add_argument('--wall',type=float,default=110);p.add_argument('--dx',type=float,default=.01);p.add_argument('--dt',type=float,default=.05);p.add_argument('--reset',action='store_true');p.add_argument('--gas',action='store_true');p.add_argument('--gas-dx',type=float,default=.01);p.add_argument('--bed',action='store_true');a=p.parse_args()
    assert a.wall<=145 and a.dx>=.0025 and a.dt<=.5
    main(a.name,a.seconds,a.wall,a.dx,a.dt,a.reset,a.gas,a.gas_dx,a.bed)
