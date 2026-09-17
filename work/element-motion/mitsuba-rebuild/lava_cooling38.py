"""Mechanism test: uniform hot 3D material, cooling and mechanics together.

No prepared cold skin, fragments, seeded damage, inlet or imposed deformation.
This suspended sample isolates thermal crust formation from ground friction.
It is a mechanism test, not the final lava shot.
"""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2',LAVA_MPM_LINEAR_BACKEND='cpu',LAVA_MPM_PRESSURE_WARM_START='1')
import argparse,json,time,traceback,hashlib
from pathlib import Path
import numpy as np
from lava_mpm import MPM,Material,block,ROOT


def run(name,spacing,until,wall,max_dt,source=None):
    folder=ROOT/'rebuild-38'/name;folder.mkdir(parents=True,exist_ok=True)
    radius=np.array([.006,.006,.005]);x=block(-radius,radius,spacing)
    x=x[(np.sum((x/radius)**2,axis=1)<1)]
    m=Material(rheology='basalt_power_creep',melt_viscosity_law='farrell_180719',fracture_length=2*spacing)
    s=MPM(x,spacing,2*spacing,temperature=1450.,material=m,origin=[-.014,-.014,-.014],shape=[20,20,20],gravity=(0,0,0),ground=False)
    provenance=None
    if source:
        parent=ROOT/source;s=MPM.load(parent);m=s.material
        provenance=dict(path=str(parent/'state.npz'),sha256=hashlib.sha256((parent/'state.npz').read_bytes()).hexdigest())
    start=time.monotonic();end=start+wall;next_frame=(np.floor(s.time/.5)+1)*.5;fail=None;rejects=0
    s.save(folder/f'frame-{round(s.time*1000):05d}');print(json.dumps(dict(particles=len(s.x),spacing=s.spacing,startTime=s.time)),flush=True)
    try:
        while s.time<until-1e-9:
            s._solve_deadline=end
            cfl=np.max(np.sum(abs(s.v)/s.cell_size,axis=1));gradient=np.linalg.norm(s.C,axis=(1,2)).max()
            dt=min(max_dt,.2/max(cfl,1e-9),.15/max(gradient,1e-9),until-s.time,next_frame-s.time)
            while True:
                try:row=s.step(dt);break
                except RuntimeError as exc:
                    rejects+=1;dt*=.5
                    print(json.dumps(dict(rejectedTime=s.time,error=str(exc),retryDt=dt)),flush=True)
                    if dt<1e-6:raise
            s.save(folder)
            t=m.temperature(s.h)
            print(json.dumps(dict(time=s.time,dt=dt,temperature=[float(t.min()),float(t.max())],solidPoints=int(s.connectivity.frozen.sum()),damage=float(s.damage.max()),broken=int(s.connectivity.broken.sum()),mechanicalResidual=row['mechanicalResidual'],thermalResidual=row['thermalBalanceRelative'],wallSeconds=time.monotonic()-start)),flush=True)
            if s.time>=next_frame-1e-9:s.save(folder/f'frame-{round(s.time*1000):05d}');next_frame+=.5
    except Exception as exc:fail=repr(exc);(folder/'failure.txt').write_text(traceback.format_exc())
    s.save(folder)
    report=dict(status='complete' if fail is None else 'failed',error=fail,time=s.time,particles=len(s.x),broken=int(s.connectivity.broken.sum()),maximumDamage=float(s.damage.max()),solidPoints=int(s.connectivity.frozen.sum()),rejects=rejects,wallSeconds=time.monotonic()-start,initialTemperatureK=1450,preparedSkin=False,authoredFragments=False,seededDamage=False,gravity=[0,0,0],source=provenance,scope='Coupled thermal/mechanical mechanism test; no production or visual acceptance')
    (folder/'proof.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='hot-start');p.add_argument('--source');p.add_argument('--spacing',type=float,default=.0015);p.add_argument('--until',type=float,default=20);p.add_argument('--wall',type=float,default=240);p.add_argument('--dt',type=float,default=.2);a=p.parse_args();run(a.name,a.spacing,a.until,a.wall,a.dt,a.source)
