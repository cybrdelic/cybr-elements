"""End-to-end cooled-crust tensile coupon. Boundary loading is explicit.

Start from actual all-molten -> cooled MPM state. No damage is seeded, no
positions are modified, and no bond is cut by this script. End grips apply
measured boundary work. Geometry must use the resulting broken topology.
"""
import argparse,hashlib,json,time
import numpy as np
from lava_mpm import ROOT,MPM
from lava_mpm_continuous import HotBed
from lava_mpm_loading import extension_grips
from lava_mpm_upper_crust import metrics
from lava_mpm_surface import extract,image_surface


def main(a):
    folder=ROOT/a.name;source=ROOT/a.source
    if (folder/'state.json').exists():s=MPM.load(folder)
    else:
        s=MPM.load(source);s.save(folder)
        cooling_setup=json.loads((source/'setup.json').read_text())
        initial=dict(source=str(source/'state.npz'),sourceSha256=hashlib.sha256((source/'state.npz').read_bytes()).hexdigest(),
            coolingSetup=cooling_setup,
            time=s.time,metrics=metrics(s),load='Opposed horizontal end grips on the cooled upper crust. This is a laboratory fracture validation, not free-flow lava motion.',
            gripSpeedMPerS=a.speed,maxDt=a.dt,seededDamage=False,prescribedCracks=False)
        (folder/'setup.json').write_text(json.dumps(initial,indent=2))
    setup=json.loads((folder/'setup.json').read_text());grips=extension_grips(.0035,.002,a.speed)
    bed=HotBed(1450.);start=time.time();n=0
    while s.time<setup['time']+a.duration-1e-9:
        cfl=np.max(np.sum(abs(s.v)/s.cell_size,axis=1));grad=np.linalg.norm(s.C,axis=(1,2)).max()
        dt=min(a.dt,.22/max(cfl,1e-4),.2/max(grad,1e-4),setup['time']+a.duration-s.time)
        s.step(dt,bed=bed,node_velocity=grips);n+=1
        if n%5==0:print(json.dumps(metrics(s)),flush=True);s.save(folder)
        if time.time()-start>a.wall:break
    # Synchronize topology after the last constitutive update, so the cache
    # cannot be one timestep behind the damage used to generate its surface.
    t=s.material.temperature(s.h)
    s.connectivity.update(s.x,s.material.solid(t),s.damage,s.principal_direction,s.sample_size,s.coherent_fraction)
    s.save(folder);surface=extract(folder/'state.npz',method='material');diagnostic=image_surface(surface)
    mesh=json.loads(surface.with_suffix('.json').read_text());measure=metrics(s)
    cooling_setup=setup.get('coolingSetup',json.loads((source/'setup.json').read_text()))
    gates=dict(initiallyMolten=cooling_setup['initialTemperatureK']>s.material.liquidus,
        cooledUpperCrust=setup['metrics']['topCoherentFraction']>.9,
        upperCrustDamage=measure['upperDamagedParticles']>0,
        upperFracture=measure['upperBrokenBonds']>0,
        noBasalFracture=measure['bottomBrokenBonds']==0,
        exportedOpening=mesh['openFacePairs']>0 and mesh['maximumOpeningM']>1e-6,
        exportedCrackWalls=mesh['crackWallTriangles']>0,
        volume=mesh['relativeVolumeDifference']<.02 and mesh['cellVolumeRelativeErrorP95']<.1,
        noInversion=mesh['minimumCellVolumeM3']>0,
        meteredLoading=s.ledger.get('prescribed_boundary_work',0)>0,
        thermalBalance=measure['thermalBalanceRelative']<1e-6)
    result=dict(status='pass' if all(gates.values()) else 'fail',gates=gates,metrics=measure,mesh=mesh,
        requestedDuration=a.duration,simulatedLoadDuration=s.time-setup['time'],
        boundaryWorkJ=s.ledger.get('prescribed_boundary_work',0),source=setup,wallSeconds=time.time()-start,
        diagnostic=str(diagnostic),limits='Validates thermally formed crust under explicit tensile grips. This does not validate spontaneous free-flow lava breakup or photorealism.')
    (folder/'proof.json').write_text(json.dumps(result,indent=2));(ROOT/'validation/upper_crust_fracture_export.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ['status','gates','metrics','boundaryWorkJ','wallSeconds','diagnostic']}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',default='upper-crust-22');p.add_argument('--name',default='upper-crust-load-22')
    p.add_argument('--duration',type=float,default=.08);p.add_argument('--speed',type=float,default=.001);p.add_argument('--wall',type=float,default=95);p.add_argument('--dt',type=float,default=.02)
    a=p.parse_args();assert a.wall<=140;main(a)
