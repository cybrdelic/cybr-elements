"""GPU-native thermomechanical lava release; no authored cracks or motion.

Finite hot volume flows over a static bed under gravity. Three-dimensional
particle conduction and surface radiation create the crust during the run.
Newton implicit elastoviscoplastic MPM carries material; local crack-band
softening models loss of cohesive strength. It is not an AT2/CD-MPM port.
"""
import os
from pathlib import Path
ROOT=Path(__file__).parent/'lava-focus/mpm/rebuild-28'
(ROOT/'compiler-temp').mkdir(parents=True,exist_ok=True)
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',TEMP=str(ROOT/'compiler-temp'),TMP=str(ROOT/'compiler-temp'))
import argparse,json,time,hashlib,traceback
import numpy as np
import warp as wp
import newton
from newton.solvers import SolverImplicitMPM
from lava_newton28_thermal import heat_step,update_material,plastic_damage,diagnostic
wp.config.kernel_cache_dir=str(ROOT/'warp-cache')


@wp.kernel
def max_speed(v:wp.array[wp.vec3],result:wp.array[float]):
    wp.atomic_max(result,0,wp.length(v[wp.tid()]))


def hashes():
    return {n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in ['lava_newton28_flow.py','lava_newton28_thermal.py']}


def run(name,pitch=.0015,until=8.,wall=120.,max_dt=.02):
    folder=ROOT/name;folder.mkdir(parents=True,exist_ok=True);wp.init()
    with wp.ScopedDevice('cuda:0'):
        source=hashes();resume=(folder/'state.npz').exists()
        if resume:
            saved=dict(np.load(folder/'state.npz'));meta=json.loads((folder/'receipt.json').read_text())
            if meta['sourceHashes']!=source or meta['pitchM']!=pitch:raise ValueError('Use a new case after changing core source or resolution')
            rest=saved['rest'];x=saved['x'];v=saved['v'];clock=float(saved['time']);rows=meta['rows'];ledger=meta['ledger']
        else:
            axes=[np.arange(-.052+pitch*.5,.038,pitch),np.arange(-.024+pitch*.5,.024,pitch),np.arange(pitch*.5,.018,pitch)]
            rest=np.array(np.meshgrid(*axes,indexing='ij')).reshape(3,-1).T.astype('f4')
            # Finite channel cross section; a rounded leading edge is an
            # initial hot volume, never a mesh used to impose later positions.
            inside=(rest[:,0]<.016)|(((rest[:,0]-.016)/.022)**2+(rest[:,1]/.024)**2<1)
            rest=rest[inside];x=rest.copy();v=np.zeros_like(x);clock=0.;rows=[]
            ledger=dict(boundaryLossJ=0.,pairConductionResidualJ=0.,plasticHeatJ=0.,fractureWorkJ=0.)
        n=len(x);voxel=pitch*2;mass=2700*pitch**3;volume=pitch**3
        if n>500000:raise ValueError('Particle budget exceeded')
        builder=newton.ModelBuilder(gravity=(1.70,0.,-9.66));SolverImplicitMPM.register_custom_attributes(builder)
        builder.add_particles(pos=x,vel=v,mass=np.full(n,mass),radius=np.full(n,pitch*.5))
        builder.add_ground_plane(cfg=newton.ModelBuilder.ShapeConfig(mu=.6))
        model=builder.finalize();a=model.state();b=model.state()
        rng=np.random.default_rng(98231)
        # Small constitutive heterogeneity represents material strength,
        # not initial damage, crack paths or positions.
        strength=saved['strength'] if resume else np.clip(rng.normal(1.,.10,n),.7,1.3).astype('f4')
        strength=wp.array(strength,dtype=float)
        h=wp.array(saved['h'] if resume else np.full(n,732220.,dtype='f4'),dtype=float)
        hnew=wp.empty_like(h)
        damage=wp.array(saved['damage'] if resume else np.zeros(n,dtype='f4'),dtype=float)
        plastic=wp.array(saved['plastic'] if resume else np.zeros(n,dtype='f4'),dtype=float)
        if resume:
            for field in ('particle_qd_grad','particle_elastic_strain','particle_Jp','particle_stress','particle_transform'):
                getattr(a.mpm,field).assign(saved[field])
        # Only material feature flags that remain enabled throughout this
        # run are cached: finite E, nonzero viscosity, no isotropic hardening.
        model.mpm.viscosity.fill_(150.);model.mpm.young_modulus.fill_(1.2e9)
        model.mpm.dilatancy.fill_(0.);model.mpm.hardening.fill_(0.)
        params=[model.mpm.young_modulus,model.mpm.poisson_ratio,model.mpm.viscosity,model.mpm.yield_pressure,model.mpm.tensile_yield_ratio,model.mpm.yield_stress,model.mpm.friction]
        wp.launch(update_material,n,inputs=[h,h,damage,strength,a.mpm.particle_elastic_strain,*params])
        solver=SolverImplicitMPM(model,SolverImplicitMPM.Config(voxel_size=voxel,tolerance=1e-5,max_iterations=200,air_drag=.001,grid_type='sparse'),verbose=False)
        grid=wp.HashGrid(128,64,64);area=wp.zeros(n);loss=wp.zeros(n);conduct=wp.zeros(n);plasticheat=wp.zeros(n);fracture=wp.zeros(n)
        tfield=wp.empty(n);coh=wp.empty(n);speed=wp.zeros(1)
        initial_energy=float(meta['initialEnergyJ']) if resume else float(np.sum(h.numpy(),dtype='f8')*mass)
        ticks=time.monotonic();error=None;steps=0;next_frame=(np.floor(clock/.5+1e-7)+1)*.5
        print(json.dumps(dict(startTime=clock,particles=n,pitchM=pitch,voxelM=voxel,device='CUDA',initial='uniformly hot, no damage, no stress' if not resume else 'resumed cache')),flush=True)

        def save(label):
            wp.launch(diagnostic,n,inputs=[h,tfield,coh]);wp.synchronize()
            state=dict(x=a.particle_q.numpy(),v=a.particle_qd.numpy(),rest=rest,h=h.numpy(),temperature=tfield.numpy(),coherence=coh.numpy(),damage=damage.numpy(),plastic=plastic.numpy(),strength=strength.numpy(),time=clock,pitch=pitch)
            for field in ('particle_qd_grad','particle_elastic_strain','particle_Jp','particle_stress','particle_transform'):state[field]=getattr(a.mpm,field).numpy()
            if not all(np.isfinite(v).all() for v in state.values()):raise RuntimeError('Nonfinite state; cache rejected')
            np.savez_compressed(folder/f'{label}.npz',**state)
            return state

        if not resume:save('frame-000000')
        try:
            while clock<until-1e-8:
                if time.monotonic()-ticks>wall:raise TimeoutError('Bounded simulation budget reached')
                speed.zero_();wp.launch(max_speed,n,inputs=[a.particle_qd,speed]);vmax=float(speed.numpy()[0])
                dt=min(max_dt,.25*voxel/max(vmax,.01),until-clock,next_frame-clock)
                if not np.isfinite(vmax) or dt<1e-6:raise RuntimeError(('Invalid velocity/CFL',vmax,dt))
                grid.build(a.particle_q,2.6*pitch)
                wp.launch(heat_step,n,inputs=[a.particle_q,h,hnew,grid.id,pitch,1.6,.94,12.,293.15,1173.15,dt,1,area,loss,conduct])
                wp.launch(update_material,n,inputs=[h,hnew,damage,strength,a.mpm.particle_elastic_strain,*params])
                solver.step(a,b,None,None,dt)
                wp.launch(plastic_damage,n,inputs=[a.mpm.particle_elastic_strain,b.mpm.particle_elastic_strain,b.mpm.particle_qd_grad,b.mpm.particle_stress,hnew,strength,damage,plastic,dt,voxel,plasticheat,fracture])
                a,b=b,a;h,hnew=hnew,h;clock+=dt;steps+=1
                # Scalar reductions keep the thermal and fracture ledgers
                # independent from beauty rendering and particle colors.
                ledger['boundaryLossJ']+=float(loss.numpy().sum(dtype='f8'))
                ledger['pairConductionResidualJ']+=float(conduct.numpy().sum(dtype='f8'))
                ledger['plasticHeatJ']+=float(plasticheat.numpy().sum(dtype='f8')*mass)
                ledger['fractureWorkJ']+=float(fracture.numpy().sum(dtype='f8')*volume)
                if clock>=next_frame-1e-8:
                    state=save(f'frame-{round(clock*1000):06d}');next_frame+=.5
                    current_energy=float(np.sum(state['h'],dtype='f8')*mass)
                    energy_error=current_energy-initial_energy+ledger['boundaryLossJ']-ledger['plasticHeatJ']-ledger['pairConductionResidualJ']
                    row=dict(time=clock,maximumDamage=float(state['damage'].max()),damagedParticles=int(np.sum(state['damage']>.9)),coherentParticles=int(np.sum(state['coherence']>.5)),minimumTemperatureK=float(state['temperature'].min()),maximumSpeedMPerS=float(np.linalg.norm(state['v'],axis=1).max()),thermalBalanceRelative=abs(energy_error)/max(initial_energy,1.),wallSeconds=time.monotonic()-ticks)
                    rows.append(row);print(json.dumps(row),flush=True)
                    if row['thermalBalanceRelative']>2e-5:raise RuntimeError(('Thermal energy acceptance failed',row))
        except Exception as exc:
            error=repr(exc);(folder/'failure.txt').write_text(traceback.format_exc())
        state=save('state')
        receipt=dict(status='complete' if error is None else 'incomplete',error=error,time=clock,target=until,steps=steps,seconds=time.monotonic()-ticks,particles=n,pitchM=pitch,voxelM=voxel,initialEnergyJ=initial_energy,ledger=ledger,rows=rows,sourceHashes=source,newtonVersion=newton.__version__,warpVersion=wp.__version__,
                     method='3D implicit elastoviscoplastic MPM; SPH enthalpy conduction; surface radiation/convection; thermal rest strain; local energy-scaled cohesive softening; no seeded damage, moving mesh, path force or painted heat.',
                     limitations='Crack-band constitutive parameters are nominal, not composition calibrated. No variational fracture convergence claim. Surface heat area uses particle occupancy gradient. Semi-infinite bed is a metered reservoir. Mechanical/plastic energy transfer is approximate. One finite volume release, not a continuous inlet.',visualStatus='unreviewed')
        (folder/'receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps({k:receipt[k] for k in ['status','error','time','steps','seconds','particles']}),flush=True)
        return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='cooling-flow');p.add_argument('--pitch',type=float,default=.0015);p.add_argument('--until',type=float,default=8.);p.add_argument('--wall',type=float,default=120.);p.add_argument('--dt',type=float,default=.02);a=p.parse_args()
    r=run(a.name,a.pitch,a.until,a.wall,a.dt);raise SystemExit(r['status']!='complete')
