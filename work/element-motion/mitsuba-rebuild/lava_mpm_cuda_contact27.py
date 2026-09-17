"""Bounded FP64 CUDA contact response, with all RHS solved in one batch.

Only linear algebra changes. The CPU Coulomb iteration and its residual,
cone and work acceptance checks remain in lava_mpm_friction.py.
"""
import os,time
import numpy as np
from lava_mpm_linear27 import cuda_runtime

STATS=dict(gpuFactors=0,seconds=0.,maximumDofs=0,maximumDirections=0,maximumTorchBytes=0,fallbacks=[])


def metrics():
    return dict(STATS,backend=os.environ.get('LAVA_MPM_FRICTION_BACKEND','cpu'),precision='float64',scope='CUDA dense contact factorization and batched response; Coulomb iteration, residual acceptance and all physics remain unchanged on CPU. Torch bytes exclude driver/context and other applications.')


class ContactResponse:
    def __init__(self,Ar,br,J):
        torch=cuda_runtime();start=time.perf_counter()
        self.scale=1/np.sqrt(np.maximum(Ar.diagonal(),1e-30))
        self.a=torch.as_tensor(np.ascontiguousarray(Ar.toarray()),device='cuda',dtype=torch.float64)
        self.sc=torch.as_tensor(self.scale[:,None],device='cuda',dtype=torch.float64)
        self.L,info=torch.linalg.cholesky_ex(self.a*self.sc*self.sc.T)
        if int(info.cpu()):raise ArithmeticError('Contact Cholesky failed SPD check')
        # One upload and two full matrix refinement passes replace dozens
        # of 16-RHS uploads and thousands of tiny CUDA triangular launches.
        B=np.column_stack([br,J.T.toarray()])
        b=torch.as_tensor(np.ascontiguousarray(B),device='cuda',dtype=torch.float64)
        y=self._solve_original(b)
        cj=torch.as_tensor(np.ascontiguousarray(J.toarray()),device='cuda',dtype=torch.float64)
        response=(cj@y).cpu().numpy()
        self.free=y[:,0].cpu().numpy()
        self.H=response[:,1:]
        torch.cuda.synchronize()
        STATS['gpuFactors']+=1;STATS['seconds']+=time.perf_counter()-start
        STATS['maximumDofs']=max(STATS['maximumDofs'],Ar.shape[0]);STATS['maximumDirections']=max(STATS['maximumDirections'],J.shape[0])
        STATS['maximumTorchBytes']=max(STATS['maximumTorchBytes'],torch.cuda.max_memory_allocated())

    def _solve_original(self,b):
        torch=cuda_runtime();y=self.sc*torch.cholesky_solve(self.sc*b,self.L)
        # Refine against the ORIGINAL system, not the rounded scaled
        # matrix. Stiff crust/melt contrasts make that distinction visible.
        for _ in range(2):y+=self.sc*torch.cholesky_solve(self.sc*(b-self.a@y),self.L)
        return y

    def solve(self,b):
        torch=cuda_runtime();start=time.perf_counter()
        y=self._solve_original(torch.as_tensor(np.ascontiguousarray(np.asarray(b).reshape(-1,1)),device='cuda',dtype=torch.float64))
        result=y[:,0].cpu().numpy()
        STATS['seconds']+=time.perf_counter()-start
        return result


def try_response(Ar,br,J):
    name=os.environ.get('LAVA_MPM_FRICTION_BACKEND','cpu')
    if name=='cpu':return None
    if name!='cuda_batched':raise ValueError('Unknown friction backend')
    torch=cuda_runtime()
    if not torch.cuda.is_available():raise RuntimeError('CUDA contact explicitly requested but unavailable')
    n=Ar.shape[0];m=J.shape[0];free,_=torch.cuda.mem_get_info()
    estimated=8*(6*n*n+8*n*(m+1)+2*m*m)
    reason=None
    # The 4,833-DOF resolved crust case is checked against CPU SuperLU in
    # lava_mpm_contact32_probe.py. Keep the conservative memory budget;
    # the old 4,096 size cutoff rejected that validated, sub-budget case.
    if n>6144 or estimated>min(free*.4,1.5*1024**3):reason='bounded dense contact size/memory gate'
    if reason is None:
        try:return ContactResponse(Ar,br,J)
        except ArithmeticError as exc:reason=str(exc)
    if len(STATS['fallbacks'])<12:STATS['fallbacks'].append(dict(dofs=n,directions=m,reason=reason))
    return None
