"""Bounded FP64 CUDA or sparse CPU linear algebra for implicit MPM.

The GPU route is conditional on both VRAM and host RAM/commit headroom.
Only linear algebra changes; physical equations and acceptance checks do not.
"""
import os,time
import numpy as np
from scipy.sparse.linalg import splu,cg,LinearOperator
from scipy.linalg import cho_solve

STATS=dict(cpuFactors=0,gpuFactors=0,cpuTriangularSolves=0,factorSeconds=0.,solveSeconds=0.,maximumDofs=0,maximumAllocatedBytes=0,fallbacks=[])
MAX_DOFS=6144
_TORCH=None
_SPARSE_CACHE={}

def available_host_memory():
    if os.name!='nt':return float('inf')
    import ctypes as c
    class Memory(c.Structure):
        _fields_=[('length',c.c_ulong),('load',c.c_ulong)]+[(k,c.c_ulonglong) for k in ('total','free','commitLimit','commitFree','virtual','virtualFree','extended')]
    value=Memory();value.length=c.sizeof(value)
    if not c.windll.kernel32.GlobalMemoryStatusEx(c.byref(value)):return 0
    return min(value.free,value.commitFree)

def cuda_runtime():
    global _TORCH
    if _TORCH is None:
        import torch
        torch.set_num_threads(2);_TORCH=torch
    return _TORCH

def backend_name():
    name=os.environ.get('LAVA_MPM_LINEAR_BACKEND','cpu')
    if name not in ('cpu','cpu_reuse','cuda_dense'):raise ValueError('Unknown MPM linear backend')
    return name

def metrics():
    return dict(STATS,backend=backend_name(),precision='float64',maximumGpuDofs=MAX_DOFS,scope='Unilateral pressure factorization and CPU substitutions only. Friction routing is recorded separately in frictionBackend; these counters exclude its factors.')

class CudaFactor:
    def __init__(self,A):
        torch=cuda_runtime();start=time.perf_counter();n=A.shape[0]
        mismatch=A-A.T
        if mismatch.nnz and np.max(abs(mismatch.data))>1e-10*max(np.max(abs(A.data)),1e-30):raise ValueError('CUDA Cholesky requires symmetric input')
        matrix=torch.as_tensor(np.ascontiguousarray(A.toarray()),device='cuda',dtype=torch.float64)
        L,info=torch.linalg.cholesky_ex(matrix,check_errors=False)
        failure=int(info.cpu())
        if failure:raise ArithmeticError(('CUDA Cholesky failed SPD check',failure))
        self.L=np.array(L.cpu().numpy(),order='F',copy=True)
        torch.cuda.synchronize();STATS['factorSeconds']+=time.perf_counter()-start
        STATS['gpuFactors']+=1;STATS['maximumDofs']=max(STATS['maximumDofs'],n)
        STATS['maximumAllocatedBytes']=max(STATS['maximumAllocatedBytes'],torch.cuda.max_memory_allocated())

    def solve(self,b):
        start=time.perf_counter();result=cho_solve((self.L,True),np.asarray(b),check_finite=False)
        STATS['cpuTriangularSolves']+=1;STATS['solveSeconds']+=time.perf_counter()-start
        return result

class ReusedSparseFactor:
    """Experimental exact-residual checked preconditioning; opt-in only."""
    def __init__(self,A,key,options):
        self.A=A;self.key=key;self.options=options;saved=_SPARSE_CACHE.get(key)
        if saved is None or saved[0]!=A.shape:self._fresh()
        else:self.preconditioner=saved[1]
    def _fresh(self):
        start=time.perf_counter();self.preconditioner=splu(self.A,**self.options)
        _SPARSE_CACHE[self.key]=(self.A.shape,self.preconditioner)
        STATS['cpuFactors']+=1;STATS['factorSeconds']+=time.perf_counter()-start
    def solve(self,b):
        b=np.asarray(b)
        if b.ndim==2:return np.column_stack([self.solve(b[:,i]) for i in range(b.shape[1])])
        norm=np.linalg.norm(b)
        if norm==0:return np.zeros_like(b)
        start=time.perf_counter();count=[0]
        def counted(_):count[0]+=1
        M=LinearOperator(self.A.shape,matvec=self.preconditioner.solve,dtype=np.float64)
        x,info=cg(self.A,b,M=M,rtol=1e-11,atol=0.,maxiter=60,callback=counted)
        residual=np.linalg.norm(self.A@x-b)/norm
        if info!=0 or not np.isfinite(residual) or residual>2e-11:
            self._fresh();x=self.preconditioner.solve(b)
            for _ in range(2):x+=self.preconditioner.solve(b-self.A@x)
            STATS['iterativeFallbacks']=STATS.get('iterativeFallbacks',0)+1
        STATS['iterativeSolves']=STATS.get('iterativeSolves',0)+1
        STATS['iterativeIterations']=STATS.get('iterativeIterations',0)+count[0]
        STATS['solveSeconds']+=time.perf_counter()-start
        return x

def factor(A,**options):
    cache_key=options.pop('_cache_key','default')
    if backend_name()=='cpu_reuse':return ReusedSparseFactor(A,cache_key,options)
    if backend_name()=='cuda_dense':
        n=A.shape[0];reason=None;needed=32*n*n
        if n>MAX_DOFS:reason='size exceeds bounded dense CUDA path'
        elif needed>available_host_memory()*.35:reason='Host RAM/commit budget for dense copies'
        if reason is None:
            torch=cuda_runtime()
            if not torch.cuda.is_available():raise RuntimeError('CUDA explicitly requested but unavailable')
            free,_=torch.cuda.mem_get_info()
            if needed>min(free*.4,1.5*1024**3):reason='insufficient memory within CUDA budget'
            else:
                try:return CudaFactor(A)
                except (ArithmeticError,MemoryError) as exc:reason=str(exc);torch.cuda.empty_cache()
        if len(STATS['fallbacks'])<12:STATS['fallbacks'].append(dict(dofs=n,reason=reason))
    STATS['cpuFactors']+=1
    return splu(A,**options)
