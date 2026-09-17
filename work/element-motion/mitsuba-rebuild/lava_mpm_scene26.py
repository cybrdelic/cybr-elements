"""CPU screening of an aged, continuously crusted lava lobe under renewed feed.

The initial thermal profile is a separate one-dimensional enthalpy solve.
It is mapped onto a stress-free, UNFRACTURED lobe, an explicit initial-condition
approximation. It is not claimed to be the complete emplacement history.
No seeded damage, fracture pattern, particle positions or forces are animated.
"""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
os.environ['CUDA_VISIBLE_DEVICES']='0' if os.environ.get('LAVA_MPM_LINEAR_BACKEND')=='cuda_dense' or os.environ.get('LAVA_MPM_FRICTION_BACKEND')=='cuda_batched' else '-1'
import argparse, hashlib, json, time, traceback
from pathlib import Path
import numpy as np
from scipy.sparse import diags
from lava_mpm import ROOT, MPM, Material, block, heat_solve, SOURCE_HASHES
from lava_mpm_inlet import emit
from lava_mpm_reservoir import HotBed


def cooled_profile(m, age=180., depth=.04, count=160):
    dz=depth/count; z=(np.arange(count)+.5)*dz
    mass=np.full(count,m.density*dz);h=m.enthalpy(np.full(count,1450.))
    c=m.conductivity/dz
    diagonal=np.full(count,2*c);diagonal[[0,-1]]=c
    K=diags([-np.full(count-1,c),diagonal,-np.full(count-1,c)],[-1,0,1]).tocsr()
    surface=np.zeros(count);surface[0]=1
    bottom=np.zeros(count);bottom[-1]=1
    initial=float(mass@h);loss=0.;t=0.
    while t<age-1e-9:
        dt=min(2.,age-t)
        h,row=heat_solve(m,h,mass,K,surface,np.full(count,m.ambient),dt,bottom,2*c,1450.)
        loss+=float(np.sum(row['radiation']+row['convection']+row['bed']));t+=dt
    return z,m.temperature(h),dict(ageSeconds=age,depthM=depth,cells=count,
        minimumTemperatureK=float(m.temperature(h).min()),
        relativeEnergyResidual=abs(float(mass@h)-initial+loss)/max(abs(initial),1.),
        method='1D finite-volume enthalpy; radiation and convection at the top; metered 1450 K reservoir at depth.')


def initial(age=180.,spacing=.008,source_interval=.25,vertical=1.):
    sample=np.array([spacing,spacing,spacing*.5*vertical]);cell=sample*2
    # 16-cm lobe: four times the depth and ten times the width of solver-25.
    radii=np.array([.080,.040,.032]);plane=-.080
    x=block([plane,-.040,0],[.080,.040,.032],sample)
    radial=np.linalg.norm(x/radii,axis=1)
    conduit=(x[:,0]<-.032)&(abs(x[:,1])<.024)&(x[:,2]<.016)
    x=x[(radial<1)|conduit];radial=np.linalg.norm(x/radii,axis=1)
    # First-order distance to ellipsoid; a hot conduit opens only upstream.
    grad=np.linalg.norm(x/radii**2,axis=1)/np.maximum(radial,1e-8)
    shell_depth=(1-radial)/np.maximum(grad,1e-8)
    tube_depth=np.minimum(.024-abs(x[:,1]),.016-x[:,2])
    depth=np.maximum(shell_depth,np.where(x[:,0]<-.032,tube_depth,-1.))
    m=Material(rheology='basalt_power_creep',melt_viscosity_law='farrell_180719',fracture_length=2*spacing)
    z,temp,thermal=cooled_profile(m,age)
    temperature=np.interp(np.maximum(depth,0),z,temp)
    # The upstream reservoir is molten. Cooling its inlet quadrature made
    # the prescribed fluid velocity pull directly on a solid plug, damaging
    # the inlet instead of pressurizing the lobe. Retain the cooled shell
    # downstream and blend to reservoir enthalpy through the supply pipe.
    reservoir=np.clip((-.032-x[:,0])/.032,0,1)
    temperature=m.temperature((1-reservoir)*m.enthalpy(temperature)+reservoir*m.enthalpy(1450.))
    # Reservoir interior remains hot; its wall retains the cooled profile.
    config=dict(plane=plane,half_width=.024,height=.016,peak_speed=.004,temperature=1450.)
    origin=np.array([-.112,-.080,-.016]);high=np.array([.176,.080,.112]);shape=np.ceil((high-origin)/cell).astype(int)+1
    s=MPM(x,sample[0],cell[0],temperature=temperature,material=m,cell_size=cell,sample_size=sample,origin=origin,shape=shape,gravity=(.855,0,-9.773),ground=True)
    setup=dict(sceneKind='aged_continuous_crust_under_renewed_feed',initialCondition='Stress-free 16 x 8 x 3.2 cm continuous lobe, zero damage and zero cracks. Temperature comes from a 1D cooling solve mapped by depth; prior 3D thermal stress history is not represented.',
        thermalProfile=thermal,reservoirInitialization='Enthalpy blends to 1450 K across x=-32 to -64 mm in the upstream pipe; fluid inlet does not grip a cold solid plug.',config=config,period=source_interval,nextEmission=source_interval,emissions=0,
        sourceQuadrature='Conservative partial-width source layers at a declared interval. This resolves mass influx before a full particle spacing has crossed the inlet; source volume is flux times elapsed interval, never a full cell per emission.',
        sourceHashes=SOURCE_HASHES,driverSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limits='Coarse mechanism screen. Nominal mixed constitutive references, no convergence or photorealism claim. No authored fracture geometry.')
    return s,setup,(z,temp)


def run(name,until,wall,dt,age=180.,spacing=.008,source_interval=.25,vertical=1.):
    folder=ROOT/'rebuild-26'/name;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'state.npz').exists():
        meta=json.loads((folder/'state.json').read_text());setup=json.loads((folder/'setup.json').read_text())
        if meta['sourceHashes']!=SOURCE_HASHES:raise ValueError('Core changed: use a new case, not stale provenance')
        s=MPM.load(folder)
    else:
        s,setup,profile=initial(age,spacing,source_interval,vertical);s.save(folder/'frame-0000')
        np.savez_compressed(folder/'initial-thermal-profile.npz',depth=profile[0],temperature=profile[1])
    (folder/'setup.json').write_text(json.dumps(setup,indent=2))
    start=time.monotonic();error=None;steps=0;next_frame=(np.floor(s.time/.25)+1)*.25
    print(json.dumps(dict(startTime=s.time,particles=len(s.x),initialTemperature=[float(s.material.temperature(s.h).min()),float(s.material.temperature(s.h).max())],thermal=setup['thermalProfile'])),flush=True)
    try:
        while s.time<until-1e-9:
            if time.monotonic()>start+wall:raise TimeoutError('Bounded CPU screen')
            if s.time>=setup['nextEmission']-1e-9:
                emit(s,setup['config'],setup['period']);setup['emissions']+=1;setup['nextEmission']+=setup['period']
            cfl=np.max(np.sum(abs(s.v)/s.cell_size,axis=1));gradient=np.linalg.norm(s.C,axis=(1,2)).max()
            step=min(dt,.2/max(cfl,1e-9),.15/max(gradient,1e-9),until-s.time,next_frame-s.time,setup['nextEmission']-s.time)
            while True:
                s._solve_deadline=start+wall
                try:row=s.step(step,bed=HotBed(1450.),boundary=setup['config']);break
                except RuntimeError:
                    step*=.5
                    if step<1e-7:raise
            steps+=1
            if s.time>=next_frame-1e-9:
                s.save(folder/f'frame-{round(s.time*1000):04d}');next_frame+=.25
                print(json.dumps(dict(time=s.time,damage=float(s.damage.max()),broken=int(s.connectivity.broken.sum()),coherent=int(s.connectivity.frozen.sum()),wallSeconds=time.monotonic()-start)),flush=True)
    except Exception as exc:
        error=repr(exc);(folder/'failure-trace.txt').write_text(traceback.format_exc())
    s.save(folder);(folder/'setup.json').write_text(json.dumps(setup,indent=2))
    proof=dict(status='pass' if error is None else 'incomplete',error=error,time=s.time,target=until,steps=steps,wallSeconds=time.monotonic()-start,
        particles=len(s.x),maximumDamage=float(s.damage.max()),brokenEdges=int(s.connectivity.broken.sum()),
        temperatureRange=[float(s.material.temperature(s.h).min()),float(s.material.temperature(s.h).max())],
        sourceHashes=SOURCE_HASHES,massErrorKg=float(s.mass.sum()-s.initial_mass-s.ledger.get('source_mass',0.)),ledger=s.ledger,
        visualStatus='unreviewed; geometry must demonstrate open fractures before a beauty render')
    from lava_mpm_linear27 import metrics
    proof['linearBackend']=metrics()
    from lava_mpm_cuda_contact27 import metrics as contact_metrics
    proof['frictionBackend']=contact_metrics()
    (folder/'proof.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof),flush=True)
    return proof


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='continuous-crust');p.add_argument('--until',type=float,default=.5);p.add_argument('--wall',type=float,default=150);p.add_argument('--dt',type=float,default=.02);p.add_argument('--age',type=float,default=180.);p.add_argument('--spacing',type=float,default=.008);p.add_argument('--source-interval',type=float,default=.25);p.add_argument('--vertical',type=float,default=1.)
    a=p.parse_args();r=run(a.name,a.until,a.wall,a.dt,a.age,a.spacing,a.source_interval,a.vertical);raise SystemExit(0 if r['status']=='pass' else 2)
