"""Bounded CUDA acceptance and comparison to the existing CPU checkpoint."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='0',LAVA_MPM_LINEAR_BACKEND='cuda_dense',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np


def components():
    from lava_mpm_rebuild25_check import pressure,mixed_contact,rock_creep
    # The historical CPU test module explicitly hides CUDA at import.
    os.environ['CUDA_VISIBLE_DEVICES']='0'
    from lava_mpm import ROOT,SOURCE_HASHES
    from lava_mpm_linear27 import metrics
    from lava_mpm_cuda_contact27 import metrics as contact_metrics
    start=time.perf_counter()
    result=dict(status='pass',pressure=pressure(),mixed_contact=mixed_contact(),rock_creep=rock_creep(),linearBackend=metrics(),frictionBackend=contact_metrics(),sourceHashes=SOURCE_HASHES,seconds=time.perf_counter()-start)
    label='gpu-batched-components' if os.environ.get('LAVA_MPM_FRICTION_BACKEND')=='cuda_batched' else 'gpu-components-current'
    (ROOT/f'rebuild-27/{label}.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


def checkpoint(case='cuda-pressure-27',cpu_case='resolved-feed',stamp=.25,same_source=False):
    from lava_mpm import ROOT,SOURCE_HASHES
    frame=f'frame-{round(stamp*1000):04d}'
    cpu=ROOT/'rebuild-26'/cpu_case/frame;gpu=ROOT/'rebuild-26'/case/frame
    a=np.load(cpu/'state.npz');b=np.load(gpu/'state.npz');am=json.loads((cpu/'state.json').read_text());bm=json.loads((gpu/'state.json').read_text())
    assert float(a['time'])==float(b['time'])==stamp and a['x'].shape==b['x'].shape
    assert am['material']==bm['material'] and am['sample_size']==bm['sample_size']
    position=float(np.linalg.norm(a['x']-b['x'],axis=1).max())
    speed=float(np.linalg.norm(a['v']-b['v'])/max(np.linalg.norm(a['v']),1e-20))
    temperature=float(abs(a['temperature']-b['temperature']).max());damage=float(abs(a['damage']-b['damage']).max())
    mass=float(abs(a['mass']-b['mass']).sum())
    checks=dict(position=position<1e-6,velocity=speed<2e-4,temperature=temperature<.002,damage=damage<2e-5,mass=mass<1e-10,
        currentGpuSource=bm['sourceHashes']==SOURCE_HASHES,temperatureBalance=bm['rows'][-1]['thermalBalanceRelative']<1e-6)
    if same_source:checks['sameCpuGpuCore']=am['sourceHashes']==bm['sourceHashes']
    report=dict(status='pass' if all(checks.values()) else 'fail',checks=checks,positionMaxErrorM=position,velocityRelativeDifference=speed,temperatureMaxErrorK=temperature,damageMaxError=damage,massDifferenceKg=mass,
        cpuSource=str(cpu),gpuSource=str(gpu),cpuStateSha256=hashlib.sha256((cpu/'state.npz').read_bytes()).hexdigest(),gpuStateSha256=hashlib.sha256((gpu/'state.npz').read_bytes()).hexdigest(),
        cpuSourceHashes=am['sourceHashes'],gpuSourceHashes=bm['sourceHashes'],linearBackend=bm['linearBackend'],
        simulatedSeconds=stamp,frictionBackend=bm.get('frictionBackend'),
        sameCore=am['sourceHashes']==bm['sourceHashes'],
        scope='Same initial condition, material, source quadrature and 0.125 s steps. Source hashes disclose whether the CPU reference is the current core or recorded older equivalent pressure-solver run. This is not spatial convergence, a long-run accuracy claim or visual approval.')
    (ROOT/f'rebuild-27/{case}-{cpu_case}-{round(stamp*1000):04d}-comparison.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True);assert report['status']=='pass'


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['components','checkpoint']);p.add_argument('--case',default='cuda-pressure-27');p.add_argument('--cpu-case',default='resolved-feed');p.add_argument('--time',type=float,default=.25);p.add_argument('--same-source',action='store_true');a=p.parse_args()
    components() if a.mode=='components' else checkpoint(a.case,a.cpu_case,a.time,a.same_source)
