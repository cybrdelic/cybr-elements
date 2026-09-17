"""CPU free-surface cooling/slump of an initially molten lava lobe.

The geometric initial condition is a single smooth deposit. Gravity, stress,
heat loss and a declared rock-bed temperature determine all subsequent motion.
No pre-broken pieces, temperature painting, forces toward target shapes or
prescribed interior velocities are used.
"""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import argparse,json,time,cProfile,pstats,io
import numpy as np
from lava_mpm import ROOT,MPM,Material,block,SOURCE_HASHES
from lava_mpm_continuous import HotBed

def initial(refine):
    sample=np.array([.002,.002,.001])/refine;cell=2*sample
    x=block([-.020,-.012,0],[.020,.012,.020],sample)
    r=(x[:,0]/.020)**2+(x[:,1]/.012)**2+(x[:,2]/.020)**2
    x=x[r<1]
    m=Material(melt_viscosity_law='farrell_180719')
    origin=np.array([-.06,-.05,-4*cell[2]]);high=np.array([.08,.05,.04]);shape=np.ceil((high-origin)/cell).astype(int)+1
    s=MPM(x,sample[0],cell[0],temperature=1468.15,material=m,ground=True,gravity=(9.81*np.sin(np.deg2rad(5)),0,-9.81*np.cos(np.deg2rad(5))),cell_size=cell,sample_size=sample,origin=origin,shape=shape)
    return s

def run(name,seconds,dt,refine,wall):
    folder=ROOT/'rebuild-25'/name;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'state.npz').exists():s=MPM.load(folder)
    else:
        s=initial(refine)
        (folder/'setup.json').write_text(json.dumps(dict(sceneKind='natural_lava_flow',initialCondition='Single 40 x 24 x 20 mm molten half-ellipsoid at 1468.15 K, initially at rest.',slopeDegrees=5,bedTemperatureK=1173.15,viscositySource='Farrell 2020 equation 3, experimental dry melt 180719',limits='Nominal equilibrium crystal fraction and rock creep/fracture parameters; not a calibrated natural basalt composition.',sourceHashes=SOURCE_HASHES),indent=2))
        s.save(folder/'frame-0000')
    bed=HotBed(1173.15);start=time.time();target=s.time+seconds;count=0;error=None;max_damage_change=0.
    try:
        while s.time<target-1e-10:
            before=s.damage.copy();step=min(dt,target-s.time)
            cfl=float(np.max(np.sum(abs(s.v)/s.cell_size,axis=1)))
            step=min(step,.2/max(cfl,1e-10))
            # Coupled solve rejects and rolls back unconverged increments.
            # This run is a fixed-resolution screening case. An independent
            # smaller-step comparison follows before claims about motion.
            for attempt in range(16):
                try:
                    s._solve_deadline=time.monotonic()+max(0,wall-(time.time()-start))
                    profile=cProfile.Profile() if count==0 else None
                    if profile is not None:profile.enable()
                    row=s.step(step,bed=bed)
                    if profile is not None:
                        profile.disable();output=io.StringIO();pstats.Stats(profile,stream=output).sort_stats('cumtime').print_stats(24)
                        (folder/'profile.txt').write_text(output.getvalue())
                    break
                except RuntimeError:
                    if profile is not None:profile.disable()
                    step*=.5
                    if step<1e-7:raise
            else:raise RuntimeError('No converged coupled increment')
            max_damage_change=max(max_damage_change,float(np.max(abs(s.damage-before))))
            count+=1
            if count%10==0 or s.time>=target-1e-10:
                s.save(folder);print(json.dumps(dict(time=s.time,particles=len(s.x),step=step,temperature=row['temperatureRange'],maxSpeed=row['maximumSpeed'],maxDamage=row['maximumDamage'],brokenEdges=row['brokenConnectivityEdges'],wallSeconds=time.time()-start)),flush=True)
            if count%25==0 or s.time>=target-1e-10:s.save(folder/f'frame-{round(s.time*1000):04d}')
            if time.time()-start>wall:raise RuntimeError('CPU screening wall budget reached')
    except Exception as exc:error=str(exc)
    s.save(folder)
    result=dict(status='pass' if error is None else 'incomplete',error=error,time=s.time,requestedTime=target,steps=count,maximumDamageIncrement=max_damage_change,wallSeconds=time.time()-start,sourceHashes=SOURCE_HASHES,limits='Screening simulation; still requires independent temporal/spatial motion comparison and visual acceptance.')
    (folder/'proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='natural-coarse');p.add_argument('--seconds',type=float,default=.1);p.add_argument('--dt',type=float,default=.02);p.add_argument('--refine',type=int,default=1);p.add_argument('--wall',type=float,default=120);a=p.parse_args();run(a.name,a.seconds,a.dt,a.refine,a.wall)
