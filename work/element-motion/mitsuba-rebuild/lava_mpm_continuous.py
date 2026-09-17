"""Continuous initially molten lava: no prescribed crust, pores or cracks."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
from lava_mpm import ROOT,MPM,block
from lava_mpm_inlet import profile,emit
from lava_mpm_fed_run import save


from lava_mpm_reservoir import HotBed


def initial(name,hz,hxy=.001):
    folder=ROOT/name;folder.mkdir(parents=True,exist_ok=True)
    # Resolve the horizontal crust as well as the vertical heat layer.
    # The previous 4 x 3 mm footprint had only ~11 x 6 cells over the flow.
    cell=np.array([hxy,hxy,hz]);sample=cell/2
    config=dict(plane=-.024,half_width=.006,height=.003,peak_speed=.006,temperature=1450.)
    p=block([-.024,-.012,0],[.020,.012,.005],sample)
    r=((p[:,0]+.006)/.027)**2+(p[:,1]/.009)**2
    top=.0044*np.sqrt(np.maximum(0,1-r))
    body=(r<1)&(p[:,2]<top)
    channel=(p[:,0]<-.012)&(abs(p[:,1])<config['half_width'])&(p[:,2]<config['height'])
    p=p[body|channel]
    origin=np.array([-.032,-.030,-4*hz]);domain_max=np.array([.068,.030,.018])
    shape=np.ceil((domain_max-origin)/cell).astype(int)+1
    s=MPM(p,sample[0],cell[0],temperature=1450.,cell_size=cell,sample_size=sample,origin=origin,shape=shape,gravity=(9.81*np.sin(np.deg2rad(8)),0,-9.81*np.cos(np.deg2rad(8))),bonded_bed=False)
    # A flowing inlet is an initial/boundary condition. Interior points start
    # at rest; no word paths, target positions or fragment trajectories.
    inside=p[:,0]<-.016;s.v[inside,0]=profile(p[inside,1],p[inside,2],config)
    setup=dict(startTime=0.,config=config,period=float(sample[0]/config['peak_speed']),nextEmission=float(sample[0]/config['peak_speed']),emissions=0,
               bedTemperatureK=1450.,description='Continuous 1450 K molten inlet above a 1450 K reservoir on an 8-degree slope. The upper and side free surfaces cool by solved radiation/convection. No initial crust pieces, pores or cracks. The reservoir is an idealized hot lower boundary, not a cold basalt plate.',cellSizeM=cell.tolist(),sampleSizeM=sample.tolist(),referenceTopology='Persistent unique material cells, including upstream inlet births')
    setup['sceneKind']='natural_lava_flow'
    (folder/'setup.json').write_text(json.dumps(setup,indent=2))
    save(s,folder,setup);return s,setup


def main(name,seconds,wall,dt,hz,hxy=.001):
    folder=ROOT/name
    if (folder/'state.npz').exists():
        setup=json.loads((folder/'inlet.json').read_text());s=MPM.load(folder)
        assert setup['stateSha256']==hashlib.sha256((folder/'state.npz').read_bytes()).hexdigest()
    else:s,setup=initial(name,hz,hxy)
    s.contact_solver='friction' if s.material.fracture_model=='phase_field' else s.contact_solver
    bed=HotBed(setup['bedTemperatureK']);target=s.time+seconds;begin=time.time();last=s.time
    history_path=folder/'source-history.json';history=json.loads(history_path.read_text()) if history_path.exists() else []
    sources=['lava_mpm.py','lava_mpm_fracture.py','lava_mpm_inlet.py','lava_mpm_continuous.py','lava_mpm_contact_admm.py']
    history.append(dict(start=s.time,hashes={q:hashlib.sha256((Path(__file__).parent/q).read_bytes()).hexdigest() for q in sources}));history_path.write_text(json.dumps(history,indent=2))
    while s.time<target-1e-8:
        if s.time>=setup['nextEmission']-1e-9:emit(s,setup['config'],setup['period']);setup['nextEmission']+=setup['period'];setup['emissions']+=1
        cfl=np.max(np.sum(abs(s.v)/s.cell_size,axis=1));grad=np.linalg.norm(s.C,axis=(1,2)).max()
        step=min(dt,.22/max(cfl,1e-4),.2/max(grad,1e-4),setup['nextEmission']-s.time,target-s.time)
        try:
            if s.material.fracture_model=='phase_field':
                from lava_mpm_coupled import advance
                advance(s,step,max_dt=step,max_wall=max(1.,wall-(time.time()-begin)),boundary=setup['config'],bed=bed)
                row=s.rows[-1]
            else:row=s.step(step,boundary=setup['config'],bed=bed)
        except Exception as exc:
            save(s,folder,setup)
            (folder/'failure.json').write_text(json.dumps(dict(error=str(exc),time=s.time,lastAcceptedStateSaved=True,productionReady=False),indent=2))
            raise
        if s.time-last>=.5 or time.time()-begin>wall:
            save(s,folder,setup);last=s.time;print(json.dumps({k:row[k] for k in ('time','particles','temperatureRange','meanSolidFraction','damagedParticles','brokenConnectivityEdges','maximumSpeed','thermalBalanceRelative','seconds')}),flush=True)
        if time.time()-begin>wall:break
    save(s,folder,setup)
    result=dict(run=name,elapsed=s.time,wallSeconds=time.time()-begin,completed=bool(s.time>=target-1e-8),latest=s.rows[-1] if s.rows else {},initialCondition=setup['description'])
    (folder/'progress.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='continuous-23');p.add_argument('--seconds',type=float,default=5);p.add_argument('--wall',type=float,default=105);p.add_argument('--dt',type=float,default=.12);p.add_argument('--hz',type=float,default=.0005);p.add_argument('--hxy',type=float,default=.001);a=p.parse_args();assert a.wall<=140 and a.dt<=.2 and a.hz>=.00025 and .0005<=a.hxy<=.001;main(a.name,a.seconds,a.wall,a.dt,a.hz,a.hxy)
