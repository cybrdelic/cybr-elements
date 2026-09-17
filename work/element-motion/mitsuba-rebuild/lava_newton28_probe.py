"""Bounded CPU/CUDA smoke and timestep probe of installed Newton MPM."""
import os
os.environ.update(OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
import argparse,json,time
from pathlib import Path
ROOT=Path(__file__).parent/'lava-focus/mpm/rebuild-28'
(ROOT/'compiler-temp').mkdir(parents=True,exist_ok=True)
os.environ.update(TEMP=str(ROOT/'compiler-temp'),TMP=str(ROOT/'compiler-temp'))
import numpy as np
import warp as wp
import newton
from newton.solvers import SolverImplicitMPM
ROOT.mkdir(parents=True,exist_ok=True)
wp.config.kernel_cache_dir=str(ROOT/'warp-cache')


def run(device):
    start=time.perf_counter();wp.init()
    with wp.ScopedDevice(device):
        h=.002;axis=(np.arange(8)+.5)*h
        x=np.array(np.meshgrid(axis,axis,axis,indexing='ij')).reshape(3,-1).T+[0,0,.04]
        b=newton.ModelBuilder();SolverImplicitMPM.register_custom_attributes(b)
        b.add_particles(pos=x,vel=np.zeros_like(x),mass=np.full(len(x),2700*h**3),radius=np.full(len(x),h*.5))
        m=b.finalize();m.set_gravity((0,0,-9.81))
        m.mpm.young_modulus.fill_(1.2e9);m.mpm.poisson_ratio.fill_(.49)
        m.mpm.viscosity.fill_(150.);m.mpm.friction.fill_(0.);m.mpm.tensile_yield_ratio.fill_(0.)
        s=SolverImplicitMPM(m,SolverImplicitMPM.Config(voxel_size=h*2,tolerance=1e-5,max_iterations=150,air_drag=1e-3,grid_type='dense' if device=='cpu' else 'sparse'))
        a=m.state();z=m.state();times=[];dt=.002
        for i in range(4):
            tick=time.perf_counter();s.step(a,z,None,None,dt);a,z=z,a;wp.synchronize();times.append(time.perf_counter()-tick)
            print(json.dumps({'step':i,'seconds':times[-1]}),flush=True)
        q=a.particle_q.numpy();v=a.particle_qd.numpy();expected_v=-9.81*dt*4;expected_drop=-9.81*dt*dt*sum(range(1,5))
        error_v=float(np.max(abs(v-np.array([0,0,expected_v]))));error_x=float(np.max(abs(q-x-np.array([0,0,expected_drop]))))
        report=dict(status='pass' if error_v<1e-5 and error_x<1e-6 else 'fail',device=device,particles=len(x),newtonVersion=newton.__version__,warpVersion=wp.__version__,gravityVelocityError=error_v,gravityPositionError=error_x,stepSeconds=times,totalSeconds=time.perf_counter()-start)
        (ROOT/f'newton-{device.replace(":","-")}-probe.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
        assert report['status']=='pass'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--device',default='cpu');a=p.parse_args();run(a.device)
