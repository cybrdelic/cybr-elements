"""Continuous hot lava feed; crust forms during the same mechanical run."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2',LAVA_MPM_LINEAR_BACKEND='cpu',LAVA_MPM_PRESSURE_WARM_START='1',LAVA_MPM_ACTIVE_FRICTION='1',LAVA_MPM_CONTACT_ACCELERATION='anderson',LAVA_MPM_CONTACT_WARM_START='1')
import argparse,json,time,traceback,hashlib,shutil
from pathlib import Path
import numpy as np
from lava_mpm import MPM,Material,block,ROOT
from lava_mpm_inlet import emit,columns
from lava_mpm_reservoir import HotBed
from lava_mpm_bed import Bed
from lava_mpm_coupled import snapshot,restore,advance


def initial_fraction(x,spacing,samples=8):
    """Volume quadrature of the continuous lobe/nozzle boundary.

    Retain partial boundary cells rather than stair-stepping the geometry
    with a binary center test. These weights set physical mass and volume;
    they are not a later render displacement or surface smoothing pass.
    """
    fractions=np.zeros(len(x));offsets=(np.arange(samples)+.5)/samples-.5
    for a in offsets:
        for b in offsets:
            for c in offsets:
                q=x+spacing*np.array([a,b,c])
                body=(np.sum(((q-[0,0,.0045])/[.012,.009,.006])**2,axis=1)<1)&(q[:,0]>=-.006)
                pipe=(q[:,0]<-.0045)&(abs(q[:,1])<.003)&(q[:,2]<.006)
                fractions+=(body|pipe)
    return fractions/samples**3


def bed_state(bed):
    return dict(origin=bed.origin.tolist(),shape=[int(v) for v in bed.shape],dx=bed.dx,
                temperature=bed.temperature.tolist(),received=bed.received,
                bottom_loss=bed.bottom_loss,time=bed.time)


def restore_bed(state):
    bed=Bed(origin=state['origin'],shape=state['shape'],dx=state['dx'])
    bed.temperature=np.array(state['temperature'])
    for k in ('received','bottom_loss','time'):setattr(bed,k,state[k])
    return bed


def run(name,until=30,wall=240,max_dt=.2,source=None,spacing=.0015,bed_kind='finite',adaptive=True):
    folder=ROOT/'rebuild-38'/name;folder.mkdir(parents=True,exist_ok=True)
    cell=2*spacing
    config=dict(plane=-.012,half_width=.003,height=.006,peak_speed=.0004,temperature=1450.,pipe_end=-.006,wall_temperature=1450.)
    x=block([-.012,-.009,0],[.012,.009,.0105],spacing)
    fraction=initial_fraction(x,spacing);keep=fraction>0;x=x[keep];fraction=fraction[keep]
    m=Material(rheology='basalt_power_creep',melt_viscosity_law='farrell_180719',fracture_length=.003)
    origin=np.array([-.018,-.015,-.009]);shape=np.rint(np.array([.072,.036,.042])/cell).astype(int)+1
    s=MPM(x,spacing,cell,temperature=1450.,material=m,origin=origin,shape=shape.tolist(),gravity=(0,0,-9.81),ground=True)
    s.volume*=fraction;s.mass*=fraction;s.F*=np.cbrt(fraction)[:,None,None]
    s.initial_mass=float(s.mass.sum());s.initial_energy=float(s.mass@s.h)
    yz,speed=columns(s.sample_size,s.cell_size,config)
    if not len(yz):raise ValueError('Inlet is unresolved')
    ancestry=None
    if source is not None:
        source=Path(source);s=MPM.load(source);m=s.material
        if not hasattr(s,'driver_state'):raise ValueError('Checkpoint has no inlet schedule; refusing an ambiguous continuation')
        config=s.driver_state['config'];ancestry=dict(path=str(source.resolve()),sha256=hashlib.sha256((source/'state.npz').read_bytes()).hexdigest())
    else:
        s.driver_state=dict(config=config,nextFrame=.5,nextEmission=.5,period=.5,bedKind=bed_kind)
        if bed_kind=='finite':
            bed=Bed(origin=[-.018,-.015,-.012],shape=np.rint(np.array([.072,.036,.012])/cell).astype(int),dx=cell)
            s.driver_state['bed']=bed_state(bed)
    bed=restore_bed(s.driver_state['bed']) if 'bed' in s.driver_state else HotBed(1450.)
    if adaptive:s.driver_state.setdefault('adaptiveFromTime',s.time)
    start=time.monotonic();end=start+wall;fail=None;rejects=0
    s.save(folder/f'frame-{round(s.time*1000):05d}');print(json.dumps(dict(particles=len(s.x),config=config)),flush=True)
    (folder/'setup.json').write_text(json.dumps(dict(config=config,initial='Uniform 1450 K connected lobe and inlet; zero damage',ground=True,period=.5),indent=2))
    try:
        while s.time<until-1e-9:
            if shutil.disk_usage(folder).free<64*1024**2:
                raise OSError('Disk safety reserve reached; pause before another simulation step')
            s._solve_deadline=end
            if s.time>=s.driver_state['nextEmission']-1e-9:
                emit(s,config,.5);s.driver_state['nextEmission']+=.5
            cfl=np.max(np.sum(abs(s.v)/s.cell_size,axis=1));gradient=np.linalg.norm(s.C,axis=(1,2)).max()
            dt=min(max_dt,.2/max(cfl,1e-9),.15/max(gradient,1e-9),until-s.time,s.driver_state['nextFrame']-s.time,s.driver_state['nextEmission']-s.time)
            while not adaptive:
                outer=snapshot(s,dict(bed=bed)) if isinstance(bed,Bed) else None
                try:
                    row=s.step(dt,boundary=config,bed=bed)
                    if isinstance(bed,Bed):
                        row['bed']=bed.advance(dt);s.driver_state['bed']=bed_state(bed)
                    break
                except RuntimeError as exc:
                    if outer is not None:restore(s,dict(bed=bed),outer)
                    rejects+=1;dt*=.5
                    print(json.dumps(dict(rejectedTime=s.time,error=str(exc),retryDt=dt)),flush=True)
                    if dt<1e-6:raise
            if adaptive:
                interval=min(until-s.time,s.driver_state['nextFrame']-s.time,s.driver_state['nextEmission']-s.time)
                validation=advance(s,interval,max_dt=dt,initial_dt=s.driver_state.get('suggestedDt'),max_wall=max(.001,end-time.monotonic()),advance_auxiliaries=isinstance(bed,Bed),bed=bed,boundary=config)
                row=s.rows[-1];dt=row['dt'];rejects+=validation['rejected']
                s.driver_state.setdefault('temporalRecords',[]).extend(validation['records'])
                s.driver_state['suggestedDt']=validation['nextDt']
                if isinstance(bed,Bed):s.driver_state['bed']=bed_state(bed)
            if s.time>=s.driver_state['nextFrame']-1e-9:
                s.driver_state['nextFrame']+=.5
                s.save(folder/f'frame-{round(s.time*1000):05d}');t=m.temperature(s.h)
                print(json.dumps(dict(time=s.time,dt=dt,temperature=[float(t.min()),float(t.max())],solidPoints=int(s.connectivity.frozen.sum()),damage=float(s.damage.max()),broken=int(s.connectivity.broken.sum()),wallSeconds=time.monotonic()-start)),flush=True)
            s.save(folder)
    except Exception as exc:fail=repr(exc);(folder/'failure.txt').write_text(traceback.format_exc())
    if fail is not None and adaptive and hasattr(s,'_adaptive_report'):
        records=s.driver_state.setdefault('temporalRecords',[]);last=records[-1]['time'] if records else -1
        records.extend(r for r in s._adaptive_report['records'] if r['time']>last+1e-10)
        s.driver_state['suggestedDt']=s._adaptive_report['nextDt']
        rejects+=s._adaptive_report['rejected']
    if isinstance(bed,Bed):s.driver_state['bed']=bed_state(bed)
    s.save(folder)
    fractured=s.connectivity.broken & s.connectivity.frozen[s.connectivity.edges].all(1)
    pause=fail is not None and (fail.startswith('TimeoutError') or 'Disk safety reserve' in fail or 'Adaptive CPU wall budget' in fail)
    report=dict(status='complete' if fail is None else 'paused' if pause else 'failed',error=fail,time=s.time,targetTime=until,particles=len(s.x),broken=int(s.connectivity.broken.sum()),fracturedSolidEdges=int(fractured.sum()),maximumDamage=float(s.damage.max()),solidPoints=int(s.connectivity.frozen.sum()),rejects=rejects,wallSeconds=time.monotonic()-start,source=ancestry,bedKind=s.driver_state.get('bedKind','hot'),temporalControl='step doubling' if adaptive else 'fixed-step control',initialTemperatureK=1450,preparedSkin=False,authoredFragments=False,seededDamage=False,scope='Coupled cooling, source flux and grounded mechanical loading. Mechanism screen, not production.')
    (folder/'proof.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='hot-fed');p.add_argument('--until',type=float,default=30);p.add_argument('--wall',type=float,default=240);p.add_argument('--source',type=Path);p.add_argument('--spacing',type=float,default=.0015);p.add_argument('--dt',type=float,default=.2);p.add_argument('--bed',choices=['hot','finite'],default='finite');p.add_argument('--fixed-step',action='store_true',help='Diagnostic control only; skips temporal error estimates');a=p.parse_args();result=run(a.name,a.until,a.wall,a.dt,source=a.source,spacing=a.spacing,bed_kind=a.bed,adaptive=not a.fixed_step)
    raise SystemExit(0 if result['status']=='complete' else 2 if result['status']=='paused' else 1)
