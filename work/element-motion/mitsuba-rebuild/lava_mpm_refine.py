"""Short material-grid comparison; records a failed gate instead of hiding it."""
import json,time,hashlib
from pathlib import Path
import numpy as np
from lava_mpm_run import initial
from lava_mpm import ROOT

def main():
    start=time.time();rows=[]
    for dx in (.01,.005):
        s=initial(dx);center0=np.average(s.x,axis=0,weights=s.mass);initial_volume=float(s.volume.sum())
        out=ROOT/f'refine-crust-{round(dx*1000):02}mm';out.mkdir(parents=True,exist_ok=True)
        target=.5
        while s.time<target-1e-9:
            speed=np.linalg.norm(s.v,axis=1).max();gradient=np.linalg.norm(s.C,axis=(1,2)).max()
            dt=min(.02,.18*dx/max(speed,.0001),.15/max(gradient,.0001),target-s.time)
            s.step(dt)
            if time.time()-start>140:
                s.save(out);raise RuntimeError('Refinement proof reached CPU budget; checkpoint saved')
        s.save(out)
        row=dict(dx=dx,particles=len(s.x),time=s.time,centerDisplacement=(np.average(s.x,axis=0,weights=s.mass)-center0).tolist(),
                 initialVolume=initial_volume,finalVolume=float(s.volume.sum()),meanTemperature=float(np.average(s.material.temperature(s.h),weights=s.mass)),
                 rmsSpeed=float(np.sqrt(np.average(np.sum(s.v*s.v,axis=1),weights=s.mass))),maximumSpeed=s.rows[-1]['maximumSpeed'])
        rows.append(row);print(json.dumps(row),flush=True)
    error=abs(rows[1]['rmsSpeed']-rows[0]['rmsSpeed'])/max(rows[1]['rmsSpeed'],1e-12)
    displacement=np.linalg.norm(np.array(rows[1]['centerDisplacement'])-rows[0]['centerDisplacement'])
    report=dict(status='pass' if error<.15 and displacement<.001 else 'fail',durationSeconds=.5,grids=rows,relativeRmsSpeedDifference=error,centerDifferenceM=float(displacement),
                scope='Early molten flow only. Does not validate long-time fracture, gas refinement, or final render quality.',seconds=time.time()-start)
    report['sourceHashes']={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('lava_mpm.py','lava_mpm_fracture.py','lava_mpm_run.py')}
    previous=ROOT/'validation'/'material_grid_refinement.json';archive=ROOT/'refinement-before-crust.json'
    if previous.exists() and not archive.exists():archive.write_text(previous.read_text())
    (ROOT/'validation'/'material_grid_refinement.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
if __name__=='__main__':main()
