"""Sparse semismooth Newton solve for compliant unilateral constraints.

Minimize .5 z^T A z - b^T z + .5 sum(max(Cz+o,0)^2 / compliance).
This is the same convex pressure/contact objective as the dense dual solve;
it does not construct a dense response matrix for every fluid pressure cell.
"""
import numpy as np
from scipy.sparse import diags
from scipy.sparse.linalg import splu


def contact(A,rhs,S,C,compliance,offset=None,initialization='bilateral'):
    Ar=(S.T@A@S).tocsc();br=np.asarray(S.T@rhs).ravel();Cr=(C@S).tocsr()
    comp=np.broadcast_to(np.asarray(compliance,dtype=float),(C.shape[0],)).copy()
    if np.any(comp<=0):raise ValueError('Strictly positive compliance required')
    offset=np.zeros(C.shape[0]) if offset is None else np.asarray(offset).ravel()
    scale=1/np.sqrt(np.maximum(Ar.diagonal(),1e-30));D=diags(scale)
    As=(D@Ar@D).tocsc();As.eliminate_zeros();Cs=(Cr@D).tocsr();bs=scale*br
    options=dict(permc_spec='MMD_AT_PLUS_A',diag_pivot_thresh=0.,options={'SymmetricMode':True})
    factor=splu(As,**options);free=factor.solve(bs);del factor
    y=free.copy()
    def quantities(q):
        value=Cs@q+offset;lam=np.maximum(value,0)/comp
        gradient=As@q-bs+Cs.T@lam
        energy=float(.5*q@(As@q)-bs@q+.5*np.sum(np.maximum(value,0)**2/comp))
        return value,lam,gradient,energy
    # An unconstrained melt can have enormous compressive velocities when
    # its bulk response lives entirely in the unilateral pressure rows.
    # Starting Newton there repeatedly rebuilds a sparse factor while the
    # line search approaches the nearly incompressible subspace. A bilateral
    # elastic predictor supplies a closer initial iterate. It is NOT the
    # answer: the original unilateral objective, residual and active-set
    # solve remain authoritative, so this does not introduce liquid tension.
    if initialization=='bilateral' and len(comp):
        H=(As+Cs.T@diags(1/comp)@Cs).tocsc()
        hs=1/np.sqrt(np.maximum(H.diagonal(),1e-30));Ds=diags(hs)
        scaled=(Ds@H@Ds).tocsc();scaled.eliminate_zeros()
        predictor_rhs=bs-Cs.T@(offset/comp)
        factor=splu(scaled,**options)
        predictor=hs*factor.solve(hs*predictor_rhs)
        predictor+=hs*factor.solve(hs*(predictor_rhs-H@predictor))
        del factor,scaled
        if quantities(predictor)[3]<quantities(y)[3]:y=predictor
    elif initialization not in ('free','bilateral'):raise ValueError('Unknown pressure initialization')
    for iteration in range(100):
        value,lam,g,energy=quantities(y)
        physical=scale*y
        residual=float(np.linalg.norm(Ar@physical+Cr.T@lam-br)/max(np.linalg.norm(br),np.linalg.norm(Cr.T@lam),1e-20))
        if residual<2e-8:break
        active=value>0;activeC=Cs[active]
        H=(As+activeC.T@diags(1/comp[active])@activeC).tocsc()
        hs=1/np.sqrt(np.maximum(H.diagonal(),1e-30));Ds=diags(hs)
        scaled=(Ds@H@Ds).tocsc();scaled.eliminate_zeros()
        fac=splu(scaled,**options);direction=-hs*fac.solve(hs*g)
        direction+=hs*fac.solve(hs*(-g-H@direction))
        # SuperLU reserves substantially more than its final L/U nonzeros.
        # Keep only one numerical factor alive across Newton iterations.
        del fac,scaled
        slope=float(g@direction)
        if slope>=0:raise RuntimeError(('Sparse pressure lost descent',slope))
        step=1.
        for backtrack in range(40):
            trial=y+step*direction;new_energy=quantities(trial)[3]
            if new_energy<=energy+1e-4*step*slope+1e-14*max(abs(energy),1e-20):break
            step*=.5
        else:raise RuntimeError('Sparse pressure line search failed')
        y=trial
    else:raise RuntimeError(('Sparse pressure did not converge',residual))
    violation=Cr@physical+offset-comp*lam
    if violation.max(initial=0)>1e-8 or not np.isfinite(physical).all():
        raise RuntimeError('Sparse pressure complementarity failed')
    delta=scale*(free-y)
    loss=max(0.,float(.5*delta@(Ar@delta)+np.sum(comp*lam*lam)))
    return S@physical,residual,lam,loss,iteration+1
