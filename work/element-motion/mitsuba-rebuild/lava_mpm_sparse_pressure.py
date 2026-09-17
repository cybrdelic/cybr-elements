"""Sparse semismooth Newton solve for compliant unilateral constraints.

Minimize .5 z^T A z - b^T z + .5 sum(max(Cz+o,0)^2 / compliance).
This is the same convex pressure/contact objective as the dense dual solve;
it does not construct a dense response matrix for every fluid pressure cell.
"""
import numpy as np
import os,time
from scipy.sparse import diags,bmat
from lava_mpm_linear27 import factor as splu
_WARM={}
STATS=dict(solves=0,iterations=0,maximumIterations=0,warmSolves=0)


def mixed_direction(As,C,comp,g):
    """Solve the same Newton equation without squaring the constraint scale.

    Elimination of the auxiliary traction recovers
    (As + C.T diag(1/comp) C) direction = -g exactly.
    Use pivoted sparse LU because the mixed block is indefinite.
    """
    from scipy.sparse.linalg import splu as pivoted_lu
    if C.shape[0]==0:return -pivoted_lu(As).solve(g)
    scale=1/np.maximum(np.sqrt(np.asarray(C.multiply(C).sum(1)).ravel()),1e-30)
    Ct=diags(scale)@C
    K=bmat([[As,Ct.T],[Ct,-diags(comp*scale*scale)]],format='csc')
    rhs=np.r_[-g,np.zeros(C.shape[0])]
    factor=pivoted_lu(K,permc_spec='COLAMD',diag_pivot_thresh=1.)
    x=factor.solve(rhs)
    for _ in range(2):x+=factor.solve(rhs-K@x)
    return x[:len(g)]


def exact_step(value,change,comp,slope,curvature):
    """Minimize the convex piecewise quadratic along a Newton direction."""
    def derivative(t):
        shift=t*change
        delta=np.where(value>0,np.maximum(shift,-value),np.maximum(value+shift,0))
        return slope+t*curvature+float(np.sum(change*delta/comp))
    lo=0.;hi=1.
    while derivative(hi)<0 and hi<64:hi*=2
    for _ in range(50):
        mid=(lo+hi)*.5
        if derivative(mid)<0:lo=mid
        else:hi=mid
    return (lo+hi)*.5


def contact(A,rhs,S,C,compliance,offset=None,_allow_warm=True,deadline=None):
    def check_deadline():
        if deadline is not None and time.monotonic()>=deadline:
            raise TimeoutError('Pressure solve deadline reached; trial must roll back')
    check_deadline()
    Ar=(S.T@A@S).tocsc();br=np.asarray(S.T@rhs).ravel();Cr=(C@S).tocsr()
    comp=np.broadcast_to(np.asarray(compliance,dtype=float),(C.shape[0],)).copy()
    if np.any(comp<=0):raise ValueError('Strictly positive compliance required')
    offset=np.zeros(C.shape[0]) if offset is None else np.asarray(offset).ravel()
    scale=1/np.sqrt(np.maximum(Ar.diagonal(),1e-30));D=diags(scale)
    As=(D@Ar@D).tocsc();As.eliminate_zeros();Cs=(Cr@D).tocsr();bs=scale*br
    options=dict(permc_spec='MMD_AT_PLUS_A',diag_pivot_thresh=0.,options={'SymmetricMode':True})
    factor=splu(As,_cache_key='momentum',**options);free=factor.solve(bs);del factor
    y=free.copy()
    def quantities(q):
        value=Cs@q+offset;lam=np.maximum(value,0)/comp
        gradient=As@q-bs+Cs.T@lam
        energy=float(.5*q@(As@q)-bs@q+.5*np.sum(np.maximum(value,0)**2/comp))
        return value,lam,gradient,energy
    key=(Ar.shape,Cr.shape,hash(S.indices.tobytes()),hash(S.indptr.tobytes()),hash(Cr.indices.tobytes()),hash(Cr.indptr.tobytes()))
    enabled=_allow_warm and os.environ.get('LAVA_MPM_PRESSURE_WARM_START')=='1'
    previous=_WARM.get(key) if enabled else None
    warm=False
    if previous is not None:
        candidate=previous/scale
        if quantities(candidate)[3]<quantities(free)[3]:y=candidate;warm=True
    for iteration in range(100):
        check_deadline()
        value,lam,g,energy=quantities(y)
        physical=scale*y
        residual=float(np.linalg.norm(Ar@physical+Cr.T@lam-br)/max(np.linalg.norm(br),np.linalg.norm(Cr.T@lam),1e-20))
        if residual<2e-8:break
        active=value>0;activeC=Cs[active]
        if os.environ.get('LAVA_MPM_PRESSURE_NEWTON')=='mixed':
            direction=mixed_direction(As,activeC,comp[active],g)
        else:
            H=(As+activeC.T@diags(1/comp[active])@activeC).tocsc()
            hs=1/np.sqrt(np.maximum(H.diagonal(),1e-30));Ds=diags(hs)
            scaled=(Ds@H@Ds).tocsc();scaled.eliminate_zeros()
            fac=splu(scaled,_cache_key='active-pressure',**options);direction=-hs*fac.solve(hs*g)
            direction+=hs*fac.solve(hs*(-g-H@direction))
            # Keep only one numerical factor across Newton iterations.
            del fac,scaled
        slope=float(g@direction)
        if slope>=0:
            if warm:return contact(A,rhs,S,C,compliance,offset,False,deadline)
            raise RuntimeError(('Sparse pressure lost descent',slope))
        step=1.;curvature=float(direction@(As@direction));constraint_direction=Cs@direction
        if os.environ.get('LAVA_MPM_PRESSURE_LINESEARCH','exact')=='exact':
            step=exact_step(value,constraint_direction,comp,slope,curvature)
        for backtrack in range(40):
            check_deadline()
            trial=y+step*direction
            # Evaluate the ENERGY CHANGE directly. Subtracting two total
            # energies near equilibrium loses the descent to cancellation,
            # making a good warm start take more iterations than a cold one.
            shift=step*constraint_direction;positive=np.maximum(value,0)
            change=np.where(value>0,np.maximum(shift,-value),np.maximum(value+shift,0))
            remainder=.5*change*change+positive*(change-shift)
            delta_energy=step*slope+.5*step*step*curvature+float(np.sum(remainder/comp))
            if delta_energy<=1e-4*step*slope:break
            step*=.5
        else:
            if warm:return contact(A,rhs,S,C,compliance,offset,False,deadline)
            raise RuntimeError('Sparse pressure line search failed')
        y=trial
    else:
        if warm:return contact(A,rhs,S,C,compliance,offset,False,deadline)
        raise RuntimeError(('Sparse pressure did not converge',residual))
    violation=Cr@physical+offset-comp*lam
    if violation.max(initial=0)>1e-8 or not np.isfinite(physical).all():
        raise RuntimeError('Sparse pressure complementarity failed')
    delta=scale*(free-y)
    loss=max(0.,float(.5*delta@(Ar@delta)+np.sum(comp*lam*lam)))
    if os.environ.get('LAVA_MPM_PRESSURE_WARM_START')=='1':_WARM.clear();_WARM[key]=physical.copy()
    STATS['solves']+=1;STATS['iterations']+=iteration+1;STATS['maximumIterations']=max(STATS['maximumIterations'],iteration+1);STATS['warmSolves']+=int(warm)
    return S@physical,residual,lam,loss,iteration+1
