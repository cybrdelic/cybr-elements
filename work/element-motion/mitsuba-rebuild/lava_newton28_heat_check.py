"""Independent energy and quadratic-field checks of the particle heat solver."""
import os
from pathlib import Path
ROOT=Path(__file__).parent/'lava-focus/mpm/rebuild-28'
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',TEMP=str(ROOT/'compiler-temp'),TMP=str(ROOT/'compiler-temp'))
import json
import numpy as np
import warp as wp
from lava_newton28_thermal import heat_step
wp.config.kernel_cache_dir=str(ROOT/'warp-cache')


def run(device='cpu'):
    wp.init()
    with wp.ScopedDevice(device):
        h=.001;axis=(np.arange(12)-5.5)*h
        x=np.array(np.meshgrid(axis,axis,axis,indexing='ij')).reshape(3,-1).T.astype('f4')
        t=1300+2e6*np.sum(x*x,axis=1);H=2800*(t-1173.15);mass=2700*h**3
        q=wp.array(x,dtype=wp.vec3);a=wp.array(H,dtype=float);b=wp.empty_like(a)
        area=wp.zeros(len(x));loss=wp.zeros(len(x));conduct=wp.zeros(len(x));grid=wp.HashGrid(32,32,32);grid.build(q,2.6*h)
        dt=.025
        wp.launch(heat_step,len(x),inputs=[q,a,b,grid.id,h,1.6,0.,0.,293.15,293.15,dt,0,area,loss,conduct])
        solved=b.numpy();inner=np.max(abs(x),axis=1)<.002
        exact_rate=6*2e6*1.6/2700
        measured=(solved[inner]-H[inner])/dt
        quadratic_error=float(abs(measured.mean()-exact_rate)/exact_rate)
        energy_error=float(abs(mass*np.sum(solved.astype('f8')-H.astype('f8'))))
        pair_sum=float(abs(conduct.numpy().astype('f8').sum()))
        wp.launch(heat_step,len(x),inputs=[q,a,b,grid.id,h,0.,.94,12.,293.15,293.15,dt,0,area,loss,conduct])
        solved=b.numpy();radiated=float(loss.numpy().astype('f8').sum());delta=mass*np.sum(solved.astype('f8')-H.astype('f8'))
        thermal_error=abs(delta+radiated)/max(radiated,1e-20)
        checks=dict(quadratic=quadratic_error<.06,pairConservation=pair_sum<1e-6,roundoffEnergy=energy_error<1e-3,radiationBalance=thermal_error<1e-3,cooling=bool(np.all(solved<=H)))
        checks={k:bool(v) for k,v in checks.items()}
        report=dict(status='pass' if all(checks.values()) else 'fail',device=device,checks=checks,particles=len(x),quadraticLaplacianRelativeError=quadratic_error,pairFluxSumJ=pair_sum,roundoffEnergyJ=energy_error,radiationBalanceRelative=float(thermal_error),estimatedAreaM2=float(area.numpy().sum()),boxAreaM2=6*(12*h)**2)
        (ROOT/f'heat-{device.replace(":","-")}.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True);assert report['status']=='pass'

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--device',default='cpu');run(p.parse_args().device)
