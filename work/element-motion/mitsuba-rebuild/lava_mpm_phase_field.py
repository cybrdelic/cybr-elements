"""CPU reference-space AT2 fracture functional with an irreversible obstacle.

E(d) = sum V [H (1-d)^2 + Gc d^2/(2 ell)]
       + (Gc ell/2) integral |grad d|^2.

The reference lattice finite-volume stencil is an explicit restriction. This
is not CD-MPM, a fitted basalt law, or an unstructured/adaptive discretization.
Fracture length is a physical model parameter, independent of grid spacing.
"""
import numpy as np
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import spsolve


def gradient_operator(rest,volume,sample,eligible):
    sample=np.broadcast_to(np.asarray(sample,dtype=float),(3,))
    base=rest.min(0);coord=np.rint((rest-base)/sample).astype(int)
    if np.max(abs(base+coord*sample-rest))>sample.min()*1e-5:
        raise ValueError('Phase field requires persistent structured reference coordinates')
    lookup={tuple(q):i for i,q in enumerate(coord)}
    if len(lookup)!=len(rest):raise ValueError('Duplicate reference coordinates in phase field')
    rows=[];cols=[];data=[]
    for a,q in enumerate(coord):
        if not eligible[a]:continue
        for axis in range(3):
            qq=q.copy();qq[axis]+=1;b=lookup.get(tuple(qq),-1)
            if b<0 or not eligible[b]:continue
            conductance=2*volume[a]*volume[b]/(volume[a]+volume[b])/sample[axis]**2
            rows.extend([a,a,b,b]);cols.extend([a,b,a,b]);data.extend([conductance,-conductance,-conductance,conductance])
    return coo_matrix((data,(rows,cols)),shape=(len(rest),len(rest))).tocsr()


def obstacle_solve(A,b,lower):
    """Bound constrained SPD M-matrix solve; report actual KKT residual."""
    d=lower.copy();active=np.ones(len(d),bool)
    diagonal=A.diagonal();scale=max(float(np.max(abs(b))),float(np.max(diagonal)),1e-30)
    for iteration in range(100):
        gradient=A@d-b
        new_active=(d<=lower+1e-12)&(gradient>=-scale*1e-12)
        free=~new_active
        trial=lower.copy()
        if free.any():trial[free]=spsolve(A[free][:,free].tocsc(),b[free]-A[free][:,new_active]@lower[new_active])
        trial=np.maximum(lower,trial)
        projected=np.where(trial<=lower+1e-12,np.minimum(A@trial-b,0),A@trial-b)
        residual=float(np.max(abs(projected))/scale)
        if residual<1e-9:
            if trial.max(initial=0)>1+1e-8:raise RuntimeError('Damage upper bound violated')
            return trial,residual,iteration+1
        if np.array_equal(new_active,active) and np.max(abs(trial-d))<1e-14:
            raise RuntimeError(('Phase obstacle stagnated',residual))
        d=trial;active=new_active
    raise RuntimeError('Phase-field obstacle did not converge')


def update_damage(rest,volume,sample,old,energy,eligible,gc,length):
    if gc<=0 or length<=0:raise ValueError('Positive fracture energy and length required')
    if not np.any(eligible):
        return np.zeros_like(old),dict(kktResidual=0.,iterations=0,fractureEnergyJ=0.,previousFractureEnergyJ=0.,incrementalEnergyBeforeJ=0.,incrementalEnergyAfterJ=0.,lengthM=length,model='reference finite-volume AT2',maximumDamageIncrement=0.)
    if np.max(sample)>length/2:
        raise ValueError('Phase-field length needs at least two material samples per ell')
    eligible=np.asarray(eligible,dtype=bool);lower=np.where(eligible,old,0.)
    H=np.where(eligible,np.maximum(energy,0.),0.)
    L=gradient_operator(rest,volume,sample,eligible)
    A=diags(volume*(gc/length+2*H))+gc*length*L;b=2*volume*H
    damage,residual,iterations=obstacle_solve(A.tocsr(),b,lower)
    def fracture(d):return float(gc/(2*length)*np.dot(volume,d*d)+gc*length/2*d@(L@d))
    def objective(d):return float(np.dot(volume,H*(1-d)**2)+fracture(d))
    before=objective(lower);after=objective(damage)
    if after>before+max(abs(before),1e-16)*1e-8:raise RuntimeError('Damage increased the incremental energy')
    return damage,dict(kktResidual=residual,iterations=iterations,fractureEnergyJ=fracture(damage),
        previousFractureEnergyJ=fracture(lower),incrementalEnergyBeforeJ=before,incrementalEnergyAfterJ=after,
        lengthM=length,model='reference finite-volume AT2',maximumDamageIncrement=float(np.max(damage-lower)))
