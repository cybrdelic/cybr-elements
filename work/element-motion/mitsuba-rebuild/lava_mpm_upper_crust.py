"""Small, fully coupled CPU surface-cooling specimen; no initial cracks.

This is a mechanism test, not a final lava shot. The substrate is a molten
reservoir at the injection temperature, rather than a cold quenching plate.
All free surfaces radiate and convect through the existing enthalpy solve.
"""
import argparse, hashlib, json, time
from pathlib import Path
import numpy as np
from lava_mpm import MPM, ROOT, block
from lava_mpm_continuous import HotBed


def initial(name, refinement=1):
    cell=np.array([.001,.001,.0005])/refinement
    sample=cell/2
    x=block([-.004,-.003,0],[.004,.003,.003],sample)
    origin=np.array([-.008,-.007,-.002])
    shape=np.ceil((np.array([.008,.007,.009])-origin)/cell).astype(int)+1
    s=MPM(x,sample[0],cell[0],temperature=1450.,cell_size=cell,
          sample_size=sample,origin=origin,shape=shape,
          gravity=(0,0,-9.81),ground=True,bonded_bed=False)
    folder=ROOT/name; s.save(folder)
    setup=dict(description='Initially molten 8 x 6 x 3 mm specimen on a 1450 K reservoir; gravity and all exposed-surface heat losses active. No initial solid, seeded damage or imposed crack opening.',
               initialTemperatureK=1450.,bedTemperatureK=1450.,cellSizeM=cell.tolist(),
               sampleSizeM=sample.tolist(),initialParticles=len(x),refinement=refinement)
    (folder/'setup.json').write_text(json.dumps(setup,indent=2))
    return s


def metrics(s):
    t=s.material.temperature(s.h); phase=s.material.solid(t)
    top=s.rest[:,2]>.0025; bottom=s.rest[:,2]<.0005
    damage=s.damage>.1; broken=s.connectivity.edges[s.connectivity.broken]
    centers=s.rest[broken].mean(1) if len(broken) else np.empty((0,3))
    return dict(time=s.time,particles=len(t),topMeanTemperatureK=float(t[top].mean()),
        bottomMeanTemperatureK=float(t[bottom].mean()),topCoherentFraction=float((phase[top]>.65).mean()),
        bottomCoherentFraction=float((phase[bottom]>.65).mean()),
        upperDamagedParticles=int((damage&top).sum()),bottomDamagedParticles=int((damage&bottom).sum()),
        upperBrokenBonds=int((centers[:,2]>.002).sum()),bottomBrokenBonds=int((centers[:,2]<.0005).sum()),
        maximumDamage=float(s.damage.max()),maximumSpeed=float(np.linalg.norm(s.v,axis=1).max()),
        thermalBalanceRelative=s.rows[-1]['thermalBalanceRelative'] if s.rows else 0.)


def main(a):
    folder=ROOT/a.name
    s=MPM.load(folder) if (folder/'state.json').exists() else initial(a.name,a.refinement)
    bed=HotBed(1450.); start=time.time(); last=s.time
    history_path=folder/'history.json'; history=json.loads(history_path.read_text()) if history_path.exists() else []
    source={q:hashlib.sha256((Path(__file__).parent/q).read_bytes()).hexdigest() for q in ['lava_mpm.py','lava_mpm_fracture.py','lava_mpm_upper_crust.py']}
    while s.time<a.until-1e-9:
        cfl=np.max(np.sum(abs(s.v)/s.cell_size,axis=1));grad=np.linalg.norm(s.C,axis=(1,2)).max()
        dt=min(a.dt,.22/max(cfl,1e-4),.2/max(grad,1e-4),a.until-s.time)
        s.step(dt,bed=bed)
        if s.time-last>=1 or time.time()-start>a.wall:
            row=metrics(s);history.append(row);s.save(folder)
            (folder/'history.json').write_text(json.dumps(history,indent=2))
            print(json.dumps(row),flush=True);last=s.time
        if time.time()-start>a.wall:break
    s.save(folder);row=metrics(s)
    report=dict(status='mechanism study, not accepted artwork',metrics=row,wallSeconds=time.time()-start,
                complete=s.time>=a.until-1e-9,sources=source)
    (folder/'progress.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='upper-crust-22');p.add_argument('--until',type=float,default=30)
    p.add_argument('--dt',type=float,default=.5);p.add_argument('--wall',type=float,default=95)
    p.add_argument('--refinement',type=int,default=1);a=p.parse_args()
    assert a.wall<=140 and 0<a.dt<=.5 and a.refinement in (1,2)
    main(a)
