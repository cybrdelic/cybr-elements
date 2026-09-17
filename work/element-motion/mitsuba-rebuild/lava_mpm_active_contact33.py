"""Active friction directions, retaining all normal pressure constraints.

Unloaded contacts have zero Coulomb radius and need no tangential unknowns.
If a condensed normal loads during the solve, its friction directions are
activated before acceptance. This is a solver reduction, not less friction.
"""
import numpy as np,time
from scipy.sparse import diags,coo_matrix
_CACHE={}

def mixed_contact(A,rhs,S,C,compliance,offset,friction,tangent_offset,physical_rows,deadline=None):
    from lava_mpm_friction import contact,tangent_rows
    from lava_mpm_sparse_pressure import contact as normal_contact
    comp=np.broadcast_to(np.asarray(compliance),(C.shape[0],));mu=np.asarray(friction)
    offset=np.asarray(offset);candidates=np.flatnonzero(mu>0)
    key=(A.shape,S.shape,C.shape,tuple(candidates))
    saved=_CACHE.get(key)
    if saved is not None and (np.linalg.norm(rhs-saved['rhs'])>.2*max(np.linalg.norm(saved['rhs']),1e-20) or np.linalg.norm(offset-saved['offset'])>.2*max(np.linalg.norm(saved['offset']),1e-8)):saved=None
    warm=saved is not None
    if warm:
        friction_ids=saved['ids'].copy();full_guess=saved['impulse'].copy();full_active=saved['active'].copy()
    else:
        normal=normal_contact(A,rhs,S,C,comp,offset,deadline=deadline)
        friction_ids=candidates[normal[2][candidates]>0]
        full_guess=np.zeros((C.shape[0],3));full_guess[:,0]=normal[2]
        full_active=np.asarray(C@normal[0]).ravel()+offset>0
        if not len(friction_ids):
            T=tangent_rows(C,mu>0);jt=np.zeros(T.shape[0])
            report=dict(iterations=normal[4],naturalResidual=normal[1],stationarity=normal[1],slidingDissipationJ=0.,maximumConeViolation=0.,pressureActiveIterations=0,condensedNormalRows=len(comp),frictionRows=0,physicalRows=physical_rows,unloadedFrictionFastPath=True)
            return (*normal,T,jt,report)
    previous=None
    for outer in range(64):
        if deadline is not None and time.monotonic()>deadline:raise TimeoutError('Active mixed contact deadline')
        normal_ids=np.setdiff1d(np.arange(C.shape[0]),friction_ids)
        active_ids=normal_ids[full_active[normal_ids]];Ca=C[active_ids];inv=1/comp[active_ids]
        condensed=A+Ca.T@diags(inv)@Ca;load=rhs-Ca.T@(offset[active_ids]*inv)
        to=np.asarray(tangent_offset).reshape(-1,2)[friction_ids].ravel()
        result=contact(condensed,load,S,C[friction_ids],comp[friction_ids],offset[friction_ids],mu[friction_ids],to,deadline,full_guess[friction_ids].ravel())
        u=result[0];q=np.asarray(C@u).ravel()+offset;updated=q>0
        lam=np.maximum(q,0)/comp;lam[friction_ids]=result[2]
        full_guess[:]=0;full_guess[:,0]=lam;full_guess[friction_ids,1:]=result[6].reshape(-1,2)
        newly_loaded=np.setdiff1d(candidates[lam[candidates]>0],friction_ids)
        if len(newly_loaded):
            friction_ids=np.union1d(friction_ids,newly_loaded);full_active=updated;previous=None;continue
        small_T=result[5].tocoo();rows=2*friction_ids[small_T.row//2]+small_T.row%2
        T=coo_matrix((small_T.data,(rows,small_T.col)),shape=(2*C.shape[0],C.shape[1])).tocsr()
        jt=full_guess[:,1:].ravel();balance=np.asarray(S.T@(A@u+C.T@lam+T.T@jt-rhs)).ravel()
        scale=max(np.linalg.norm(S.T@rhs),np.linalg.norm(S.T@(C.T@lam)),1e-20)
        error=float(np.linalg.norm(balance)/scale)
        if np.array_equal(updated[normal_ids],full_active[normal_ids]) and error<1e-5:
            _CACHE.clear();_CACHE[key]=dict(ids=friction_ids.copy(),impulse=full_guess.copy(),active=updated.copy(),rhs=rhs.copy(),offset=offset.copy())
            report=dict(result[7],stationarity=error,pressureActiveIterations=outer+1,condensedNormalRows=len(normal_ids),frictionRows=len(friction_ids),candidateFrictionRows=len(candidates),physicalRows=physical_rows)
            return u,error,lam,result[3]+float(np.sum(comp[normal_ids]*lam[normal_ids]**2)),result[4],T,jt,report
        if previous is not None and np.array_equal(updated[normal_ids],previous[normal_ids]):
            if warm:
                _CACHE.clear();return mixed_contact(A,rhs,S,C,compliance,offset,friction,tangent_offset,physical_rows,deadline)
            raise RuntimeError(('Active pressure set cycled',error))
        previous=full_active.copy();full_active=updated
    raise RuntimeError(('Active mixed contact did not converge',error))
