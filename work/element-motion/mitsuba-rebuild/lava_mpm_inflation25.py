"""CPU-fed lava lobe: mass/enthalpy enter through a physical inlet.

No initialized crust, cracks, damage, target geometry or interior forces.
This is a bounded screening run, not a convergence certificate.
"""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import argparse,hashlib,json,time,traceback
import numpy as np
from lava_mpm import ROOT,MPM,Material,block,SOURCE_HASHES
from lava_mpm_inlet import emit,profile
from lava_mpm_continuous import HotBed


def initial():
    sample=np.array([.001,.001,.0005]);cell=sample*2
    config=dict(plane=-.010,half_width=.003,height=.003,peak_speed=.001,temperature=1450.)
    x=block([-.010,-.004,0],[.008,.004,.004],sample)
    lobe=((x[:,0]+.001)/.007)**2+(x[:,1]/.004)**2+(x[:,2]/.004)**2<1
    conduit=(x[:,0]<-.002)&(abs(x[:,1])<.003)&(x[:,2]<.003)
    x=x[lobe|conduit]
    m=Material(rheology='basalt_power_creep',melt_viscosity_law='farrell_180719',fracture_length=.002)
    origin=np.array([-.018,-.014,-.002]);high=np.array([.040,.014,.016]);shape=np.ceil((high-origin)/cell).astype(int)+1
    s=MPM(x,sample[0],cell[0],temperature=1450.,material=m,cell_size=cell,sample_size=sample,origin=origin,shape=shape,gravity=(.855,0,-9.773),ground=True)
    # Inlet flow is already established only in the upstream conduit.
    upstream=x[:,0]<-.006;s.v[upstream,0]=profile(x[upstream,1],x[upstream,2],config)
    period=sample[0]/config['peak_speed']
    setup=dict(sceneKind='natural_lava_flow',config=config,period=period,nextEmission=period,emissions=0,bedTemperatureK=1450.,
        initialCondition='Initially molten 1450 K lobe and conduit. Zero initial damage, cracks and crust; prescribed parabolic flow only at the upstream inlet.',
        source='Conservative inlet quadrature, positive mass/enthalpy/momentum and boundary-work ledgers. No interior attractors or timed fractures.',
        references='Farrell dry experimental melt; Violay glass-free basalt creep reference. Mixed constitutive references, not calibrated free-surface basalt.',sourceHashes=SOURCE_HASHES)
    return s,setup


def run(name,until,wall,dt,source=None):
    folder=ROOT/'rebuild-25'/name;folder.mkdir(exist_ok=True,parents=True)
    if (folder/'state.npz').exists():
        if json.loads((folder/'state.json').read_text()).get('sourceHashes')!=SOURCE_HASHES:raise ValueError('Solver changed; preserve this run and start a new one')
        s=MPM.load(folder);setup=json.loads((folder/'setup.json').read_text())
    elif source is not None:
        parent=ROOT/'rebuild-25'/source;s=MPM.load(parent);setup=json.loads((parent/'setup.json').read_text())
        setup['continuation']=dict(parentState=str(parent/'state.npz'),parentStateSha256=hashlib.sha256((parent/'state.npz').read_bytes()).hexdigest(),parentSourceHashes=json.loads((parent/'state.json').read_text()).get('sourceHashes'),startTime=s.time,change='Equivalent contact response evaluated in bounded RHS batches; all material equations, states and boundary conditions retained.',sourceHashes=SOURCE_HASHES)
        s.save(folder/f'frame-{round(s.time*1000):04d}')
    else:
        s,setup=initial();s.save(folder/'frame-0000')
    bed=HotBed(setup['bedTemperatureK']);start=time.monotonic();error=None;frames=2*(np.floor(s.time/2)+1);steps=0
    try:
        while s.time<until-1e-9:
            if time.monotonic()>start+wall:raise TimeoutError('CPU screening budget reached')
            if s.time>=setup['nextEmission']-1e-9:
                emit(s,setup['config'],setup['period']);setup['emissions']+=1;setup['nextEmission']+=setup['period']
            cfl=np.max(np.sum(abs(s.v)/s.cell_size,axis=1));gradient=np.linalg.norm(s.C,axis=(1,2)).max()
            step=min(dt,.2/max(cfl,1e-9),.15/max(gradient,1e-9),until-s.time,frames-s.time,setup['nextEmission']-s.time)
            while True:
                s._solve_deadline=start+wall
                try:row=s.step(step,bed=bed,boundary=setup['config']);break
                except RuntimeError:
                    step*=.5
                    if step<1e-7:raise
            steps+=1
            if s.time>=frames-1e-9:
                dest=folder/f'frame-{round(s.time*1000):04d}';s.save(dest);(dest/'setup.json').write_text(json.dumps(setup,indent=2));frames+=2
                print(json.dumps(dict(time=s.time,particles=len(s.x),temperature=row['temperatureRange'],coherent=int(s.connectivity.frozen.sum()),damage=float(s.damage.max()),brokenEdges=int(s.connectivity.broken.sum()),speed=row['maximumSpeed'],massError=row['massBalanceErrorKg'],wallSeconds=time.monotonic()-start)),flush=True)
    except Exception as exc:
        error=repr(exc);(folder/'failure-trace.txt').write_text(traceback.format_exc())
    s.save(folder);(folder/'setup.json').write_text(json.dumps(setup,indent=2))
    result=dict(status='pass' if error is None else 'incomplete',error=error,time=s.time,targetTime=until,steps=steps,particles=len(s.x),temperatureRange=[float(s.material.temperature(s.h).min()),float(s.material.temperature(s.h).max())],maximumDamage=float(s.damage.max()),brokenEdges=int(s.connectivity.broken.sum()),coherentParticles=int(s.connectivity.frozen.sum()),
        ledger=s.ledger,massErrorKg=float(s.mass.sum()-s.initial_mass-s.ledger.get('source_mass',0)),thermalBalanceRelative=s.rows[-1]['thermalBalanceRelative'] if s.rows else 0,wallSeconds=time.monotonic()-start,sourceHashes=SOURCE_HASHES,limits='Coarse CPU physical screening, not a final render or spatial/temporal convergence proof.')
    (folder/'proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='fed-basalt');p.add_argument('--until',type=float,default=12);p.add_argument('--wall',type=float,default=120);p.add_argument('--dt',type=float,default=.25);p.add_argument('--source');a=p.parse_args();result=run(a.name,a.until,a.wall,a.dt,a.source)
    raise SystemExit(0 if result['status']=='pass' else 2)
