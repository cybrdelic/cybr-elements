"""A hot inlet feeding an actually simulated, previously cooled lava sample."""
import json,time,argparse,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from lava_mpm import ROOT,MPM,block
from lava_mpm_inlet import profile,emit


def save(s,folder,setup):
    s.save(folder)
    setup['stateSha256']=hashlib.sha256((folder/'state.npz').read_bytes()).hexdigest()
    tmp=folder/'inlet.partial.json';tmp.write_text(json.dumps(setup,indent=2));tmp.replace(folder/'inlet.json')
    target=folder/f'frame-{round((s.time-setup["startTime"])*1000):06}.npz'
    np.savez_compressed(target,**dict(np.load(folder/'state.npz')))


def main(name,seconds,wall,dt,conduit=False):
    folder=ROOT/name;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'state.npz').exists():
        setup=json.loads((folder/'inlet.json').read_text())
        if setup['stateSha256']!=hashlib.sha256((folder/'state.npz').read_bytes()).hexdigest():raise RuntimeError('Inlet manifest and material checkpoint disagree; do not duplicate source material')
        s=MPM.load(folder)
    else:
        source=ROOT/'crust-local-10';s=MPM.load(source)
        config=dict(plane=-.08,half_width=.015,height=.025,peak_speed=.08,temperature=1450.)
        if conduit:config.update(height=.02,pipe_end=-.05)
        x=block([config['plane'],-config['half_width'],0],[config.get('pipe_end',-.044),config['half_width'],config['height']],s.spacing)
        distance,_=cKDTree(s.x).query(x);x=x[distance>=s.spacing*.98]
        v=np.zeros_like(x);v[:,0]=profile(x[:,1],x[:,2],config)
        s.add_particles(x,v,np.full(len(x),config['temperature']),np.full(len(x),s.spacing**3),source_kind='prefill')
        period=s.spacing/config['peak_speed']
        setup=dict(startTime=s.time,config=config,period=period,nextEmission=s.time+period,emissions=0,
                   seed=dict(source=str(source/'state.npz'),sha256=hashlib.sha256((source/'state.npz').read_bytes()).hexdigest(),hotChannelParticles=len(x)),
                   description='New inlet experiment: an initially hot channel feeds the cached cooling sample. Initial channel mass/enthalpy is declared; subsequent material enters through a prescribed-velocity boundary. No fragment paths or geometric crack cuts.')
        save(s,folder,setup)
    config=setup['config'];start=time.time();target=s.time+seconds;last_save=s.time
    history_path=folder/'source-history.json';history=json.loads(history_path.read_text()) if history_path.exists() else []
    scripts=['lava_mpm.py','lava_mpm_fracture.py','lava_mpm_inlet.py','lava_mpm_fed_run.py']
    history.append(dict(startTime=s.time,hashes={k:hashlib.sha256((Path(__file__).parent/k).read_bytes()).hexdigest() for k in scripts}));history_path.write_text(json.dumps(history,indent=2))
    while s.time<target-1e-9:
        if s.time>=setup['nextEmission']-1e-9:
            emit(s,config,setup['period']);setup['nextEmission']+=setup['period'];setup['emissions']+=1
        speed=np.linalg.norm(s.v,axis=1).max();gradient=np.linalg.norm(s.C,axis=(1,2)).max()
        step=min(dt,.18*s.dx/max(speed,.0001),.15/max(gradient,.0001),target-s.time,setup['nextEmission']-s.time)
        row=s.step(step,boundary=config)
        if s.x[:,0].min()<config['plane']-s.dx*.2:raise RuntimeError('Material crossed the inlet boundary beyond the grid tolerance')
        if row['maximumSpeed']>2:raise RuntimeError('Inlet study exceeded its 2 m/s stability gate; no final frame accepted')
        if s.time-last_save>=.1 or time.time()-start>=wall:
            save(s,folder,setup);last_save=s.time
            print(json.dumps(dict(elapsed=s.time-setup['startTime'],particles=len(s.x),speed=row['maximumSpeed'],broken=row['brokenConnectivityEdges'],massError=row['massBalanceErrorKg'],heatError=row['thermalBalanceRelative'],stepSeconds=row['seconds'])),flush=True)
        if time.time()-start>=wall:break
    save(s,folder,setup)
    result=dict(run=name,elapsed=float(s.time-setup['startTime']),physicalTime=float(s.time),particles=len(s.x),seconds=time.time()-start,completed=bool(s.time>=target-1e-9),latest=s.rows[-1],ledger=s.ledger)
    (folder/'progress.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='inlet-crust-12');p.add_argument('--seconds',type=float,default=.8);p.add_argument('--wall',type=float,default=105);p.add_argument('--dt',type=float,default=.02);p.add_argument('--conduit',action='store_true');a=p.parse_args();assert a.wall<=140 and a.dt<=.05;main(a.name,a.seconds,a.wall,a.dt,a.conduit)
