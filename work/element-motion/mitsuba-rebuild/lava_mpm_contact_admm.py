"""Sparse primal ADMM for the same compliant unilateral-contact objective."""
import numpy as np
from scipy.sparse import diags
from scipy.sparse.linalg import splu


def contact(A,rhs,S,C,compliance,offset=None):
    Ar=(S.T@A@S).tocsc();br=S.T@rhs;Cr=(C@S).tocsr();n=C.shape[0]
    if n==0:
        z=splu(Ar).solve(br);return S@z,0.,np.zeros(0),0.,0
    offset=np.zeros(n) if offset is None else np.asarray(offset)
    diag=1/np.sqrt(np.maximum(Ar.diagonal(),1e-30));D=diags(diag);As=(D@Ar@D).tocsc();Cs=(Cr@D).tocsr();bs=diag*br
    freefactor=splu(As);free=freefactor.solve(bs)
    freeq=Cs@free+offset
    if np.max(freeq,initial=0)<=1e-9:return S@(diag*free),0.,np.zeros(n),0.,0
    # Contact responses are only estimated for penalty selection. The final
    # solve uses the full sparse elastic/viscous matrix, never a lumped body.
    rng=np.random.default_rng(803);estimate=np.zeros(n)
    for _ in range(6):
        r=rng.choice([-1.,1.],n);estimate+=r*(Cs@freefactor.solve(Cs.T@r))/6
    positive=estimate[estimate>0];rho=1/max(float(np.median(positive)) if len(positive) else 1.,1e-9)
    epsilon=compliance
    q=np.minimum(freeq,0);u=np.zeros(n);z=free.copy();last_rho=None;fac=None
    for iteration in range(1,1201):
        if rho!=last_rho:
            system=(As+rho*(Cs.T@Cs)).tocsc();sc=1/np.sqrt(system.diagonal());Ds=diags(sc);fac=splu((Ds@system@Ds).tocsc());last_rho=rho
        b=bs+rho*Cs.T@(q-offset-u)
        z=sc*fac.solve(sc*b)
        # One refinement pass controls cancellation in stiff cold material.
        z+=sc*fac.solve(sc*(b-system@z))
        value=Cs@z+offset;previous=q.copy();over=1.5*value-.5*previous
        candidate=over+u;q=np.where(candidate>0,candidate*(rho*epsilon/(1+rho*epsilon)),candidate);u+=over-q
        multiplier=rho*u;primal=value-q
        if iteration%10==0:
            physical=diag*z;residual=float(np.linalg.norm(Ar@physical+Cr.T@multiplier-br)/max(np.linalg.norm(br),1e-30))
            gap=float(np.max(value-epsilon*multiplier,initial=0));negative=float(-np.min(multiplier,initial=0))
            complement=float(np.max(abs(multiplier*(value-epsilon*multiplier)),initial=0))
            if residual<3e-6 and gap<2e-7 and negative<1e-10 and complement<1e-9:break
        if iteration%40==0:
            p=float(np.linalg.norm(primal));d=float(np.linalg.norm(rho*Cs.T@(q-previous)));old=rho
            if p>10*d:rho*=2
            elif d>10*p:rho*=.5
            if rho!=old:u*=old/rho
    else:raise RuntimeError(('Sparse contact did not converge',residual,gap,complement,rho))
    delta=diag*(free-z);loss=max(0,float(.5*delta@(Ar@delta)+np.sum(epsilon*multiplier*multiplier)))
    return S@(diag*z),residual,multiplier,loss,iteration
