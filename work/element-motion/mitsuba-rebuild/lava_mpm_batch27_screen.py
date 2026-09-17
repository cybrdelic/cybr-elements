"""Capture one real contact system; benchmark identical bulk responses."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import argparse,json,time
from pathlib import Path
import numpy as np
from scipy.sparse import load_npz,save_npz,diags,vstack
from scipy.sparse.linalg import splu
ROOT=Path(__file__).parent/'lava-focus/mpm/rebuild-27/batched-contact'


def capture():
    from lava_mpm_scene26 import initial
    from lava_mpm_reservoir import HotBed
    import lava_mpm_friction as friction
    class Captured(BaseException):pass
    def record(A,rhs,S,C,compliance,offset=None,friction=None,tangent_offset=None,deadline=None):
        ROOT.mkdir(parents=True,exist_ok=True)
        for key,value in dict(A=A,S=S,C=C).items():save_npz(ROOT/f'{key}.npz',value)
        np.savez_compressed(ROOT/'vectors.npz',rhs=rhs,compliance=compliance,offset=offset,friction=friction,tangent_offset=tangent_offset)
        from lava_mpm import SOURCE_HASHES
        report=dict(shape=A.shape,nonzeros=A.nnz,physicalContactRows=C.shape[0],sourceHashes=SOURCE_HASHES,scope='First condensed Coulomb system from the aged unfractured lobe; captured before solving, no simulation checkpoint produced.')
        (ROOT/'input.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
        raise Captured()
    friction.contact=record
    state,setup,_=initial()
    try:state.step(.125,bed=HotBed(1450.),boundary=setup['config'])
    except Captured:pass
    else:raise AssertionError('No actual friction system captured')


def data():
    A=load_npz(ROOT/'A.npz');S=load_npz(ROOT/'S.npz');C=load_npz(ROOT/'C.npz');v=np.load(ROOT/'vectors.npz')
    from lava_mpm_friction import tangent_rows
    Ar=(S.T@A@S).tocsc();br=np.asarray(S.T@v['rhs']);Cn=(C@S).tocsr();Ct=(tangent_rows(C,v['friction']>0)@S).tocsr();count=C.shape[0]
    order=np.array([[i,count+2*i,count+2*i+1] for i in range(count)]).ravel()
    J=vstack([Cn,Ct],format='csr')[order]
    return Ar,br,J


def benchmark():
    import torch
    torch.set_num_threads(2)
    Ar,br,J=data();scale=1/np.sqrt(np.maximum(Ar.diagonal(),1e-30));D=diags(scale);As=(D@Ar@D).tocsc()
    B=np.column_stack([br,J.T.toarray()]);bs=scale[:,None]*B
    start=time.perf_counter();fac=splu(As,permc_spec='MMD_AT_PLUS_A',diag_pivot_thresh=0.,options={'SymmetricMode':True})
    z=scale[:,None]*fac.solve(bs)
    for _ in range(2):z+=scale[:,None]*fac.solve(scale[:,None]*(B-Ar@z))
    reference=J@z;cpu=time.perf_counter()-start
    rows=[]
    for trial in range(2):
        start=time.perf_counter()
        a=torch.as_tensor(np.ascontiguousarray(As.toarray()),device='cuda',dtype=torch.float64)
        b=torch.as_tensor(np.ascontiguousarray(bs),device='cuda',dtype=torch.float64)
        c=torch.as_tensor(np.ascontiguousarray(J.toarray()*scale),device='cuda',dtype=torch.float64)
        L,info=torch.linalg.cholesky_ex(a);assert int(info.cpu())==0
        y=torch.cholesky_solve(b,L)
        for _ in range(2):y+=torch.cholesky_solve(b-a@y,L)
        response=(c@y).cpu().numpy();torch.cuda.synchronize()
        seconds=time.perf_counter()-start
        relative=float(np.linalg.norm(response-reference)/np.linalg.norm(reference))
        normalizedResidual=float(torch.linalg.norm(b-a@y).cpu()/torch.linalg.norm(b).cpu())
        assert relative<2e-6 and normalizedResidual<2e-6,(relative,normalizedResidual)
        rows.append(dict(seconds=seconds,relativeDifference=relative,normalizedResidual=normalizedResidual,peakTorchBytes=torch.cuda.max_memory_allocated()))
    report=dict(status='pass',dofs=Ar.shape[0],contactDirections=J.shape[0],cpuBulkSeconds=cpu,gpuTrials=rows,scope='FP64 factorization, all contact RHS together, two refinement passes, and J-response. Includes matrix transfers. This is one real matrix, not full-simulation timing.')
    (ROOT/'benchmark.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)


def solve_check():
    from lava_mpm_friction import contact
    from lava_mpm import SOURCE_HASHES
    os.environ['CUDA_VISIBLE_DEVICES']='0'
    from lava_mpm_cuda_contact27 import metrics
    from lava_mpm_linear27 import cuda_runtime
    init=time.perf_counter();cuda_runtime().empty(1,device='cuda');cuda_runtime().cuda.synchronize();initialization=time.perf_counter()-init
    A=load_npz(ROOT/'A.npz');S=load_npz(ROOT/'S.npz');C=load_npz(ROOT/'C.npz');v=np.load(ROOT/'vectors.npz')
    results=[];times=[]
    for backend in ('cpu','cuda_batched'):
        os.environ['LAVA_MPM_FRICTION_BACKEND']=backend
        start=time.perf_counter()
        r=contact(A,v['rhs'],S,C,v['compliance'],v['offset'],v['friction'],v['tangent_offset'],time.monotonic()+45)
        times.append(time.perf_counter()-start);results.append(r)
    a,b=results;error=float(np.linalg.norm(a[0]-b[0])/max(np.linalg.norm(a[0]),1e-30))
    absolute=float(np.max(abs(a[0]-b[0])))
    checks=dict(velocity=error<2e-4,absoluteVelocity=absolute<1e-7,stationarity=b[-1]['stationarity']<1e-5,cone=b[-1]['maximumConeViolation']<1e-8,naturalResidual=b[-1]['naturalResidual']<2e-8)
    report=dict(status='pass' if all(checks.values()) else 'fail',checks=checks,velocityRelativeDifference=error,velocityMaximumErrorMPerS=absolute,cpuSeconds=times[0],cudaSeconds=times[1],cudaInitializationSeconds=initialization,cpuContact=a[-1],gpuContact=b[-1],backend=metrics(),sourceHashes=SOURCE_HASHES,scope='Complete first real Coulomb contact solve, same matrix and constraints. CUDA runtime initialization measured separately. One-system speedup does not establish whole-MPM speedup.')
    (ROOT/'solve-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
    assert report['status']=='pass'


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['capture','benchmark','solve']);args=p.parse_args()
    {'capture':capture,'benchmark':benchmark,'solve':solve_check}[args.mode]()
