"""Resolved continuous crust with active, sparse selection of friction directions."""
import os
os.environ['LAVA_MPM_ACTIVE_FRICTION']='1'
os.environ['LAVA_MPM_PRESSURE_WARM_START']='1'
from lava_mpm_scene32 import initial
from lava_mpm import ROOT,MPM,SOURCE_HASHES
from lava_mpm_reservoir import HotBed
from lava_mpm_inlet import emit
import numpy as np,json,time,hashlib,argparse,traceback

def run(name,until,wall,dt,source=None):
    folder=ROOT/'rebuild-33'/name;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'state.npz').exists():
        meta=json.loads((folder/'state.json').read_text());setup=json.loads((folder/'setup.json').read_text())
        if meta['sourceHashes']!=SOURCE_HASHES:raise ValueError('Source changed; use an explicitly documented migration')
        s=MPM.load(folder)
    elif source:
        p=ROOT/source;s=MPM.load(p);setup=json.loads((p/'setup.json').read_text())
        setup['continuationSource']=dict(path=str(p/'state.npz'),sha256=hashlib.sha256((p/'state.npz').read_bytes()).hexdigest(),reason='Same physical equations and unchanged acceptance thresholds; active contact reduction validated against the unreduced solver.')
        if setup['emissions']==0:setup.update(period=.2,nextEmission=.2)
    else:
        s,setup,_=initial(source_interval=.2)
    # Check the next source layer before spending time on a mechanical run.
    import copy
    from lava_mpm_phase_field import gradient_operator
    probe=copy.deepcopy(s);emit(probe,setup['config'],setup['period'])
    gradient_operator(probe.rest,probe.volume,probe.sample_size,np.ones(len(probe.x),bool));del probe
    setup['nextSourceLatticeValidated']=True
    (folder/'setup.json').write_text(json.dumps(setup,indent=2));s.save(folder)
    start=time.monotonic();error=None;steps=0;next_frame=(np.floor(s.time/.2)+1)*.2
    print(json.dumps(dict(startTime=s.time,particles=len(s.x))),flush=True)
    try:
        while s.time<until-1e-9:
            if time.monotonic()>start+wall:raise TimeoutError('Case wall limit')
            if s.time>=setup['nextEmission']-1e-9:
                emit(s,setup['config'],setup['period']);setup['emissions']+=1;setup['nextEmission']+=setup['period']
            cfl=np.max(np.sum(abs(s.v)/s.cell_size,axis=1));gradient=np.linalg.norm(s.C,axis=(1,2)).max()
            h=min(dt,.2/max(cfl,1e-9),.15/max(gradient,1e-9),until-s.time,next_frame-s.time,setup['nextEmission']-s.time)
            while True:
                s._solve_deadline=start+wall
                try:r=s.step(h,bed=HotBed(1450.),boundary=setup['config']);break
                except RuntimeError as exc:
                    print(json.dumps(dict(rejectedTime=s.time,dt=h,error=str(exc))),flush=True);h*=.5
                    if h<1e-7:raise
            steps+=1
            print(json.dumps(dict(time=s.time,dt=h,damage=float(s.damage.max()),broken=int(s.connectivity.broken.sum()),coupling=r.get('damageCouplingIterations'),friction=r.get('frictionContact'),wallSeconds=time.monotonic()-start)),flush=True)
            s.save(folder);(folder/'setup.json').write_text(json.dumps(setup,indent=2))
            if s.time>=next_frame-1e-9:s.save(folder/f'frame-{round(s.time*1000):04d}');next_frame+=.2
    except Exception as exc:error=repr(exc);(folder/'failure-trace.txt').write_text(traceback.format_exc())
    s.save(folder);(folder/'setup.json').write_text(json.dumps(setup,indent=2))
    proof=dict(status='complete' if error is None else 'incomplete',time=s.time,target=until,error=error,steps=steps,particles=len(s.x),damage=float(s.damage.max()),broken=int(s.connectivity.broken.sum()),wallSeconds=time.monotonic()-start,sourceHashes=SOURCE_HASHES,visualStatus='Not yet reviewed')
    (folder/'proof.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='active-contact');p.add_argument('--source');p.add_argument('--until',type=float,default=2);p.add_argument('--wall',type=float,default=600);p.add_argument('--dt',type=float,default=.05);a=p.parse_args();run(a.name,a.until,a.wall,a.dt,a.source)
