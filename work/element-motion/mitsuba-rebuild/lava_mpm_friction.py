"""Implicit Coulomb stick/slip using the full mechanical contact response.

Normal complementarity and maximum tangential dissipation are solved together.
This is non-associated Coulomb contact (no cone-induced normal dilatancy), not
the convex relaxed contact model from Drake. No post-solve velocity clipping.
"""
import numpy as np
import os
import time
from numba import njit
from scipy.sparse import coo_matrix,diags
from scipy.sparse.linalg import splu

# Initial guesses only. Every returned solution still satisfies the original
# pressure/contact equations. Never cache a velocity or accepted physical state.
_PRESSURE_GUESS={}


def tangent_rows(C,enabled=None):
    C=C.tocsr();rows=[];cols=[];values=[]
    for row in range(C.shape[0]):
        if enabled is not None and not enabled[row]:continue
        indices=C.indices[C.indptr[row]:C.indptr[row+1]];data=C.data[C.indptr[row]:C.indptr[row+1]]
        nodes=np.unique(indices//3);vectors=np.zeros((len(nodes),3));lookup={int(k):i for i,k in enumerate(nodes)}
        for k,v in zip(indices,data):vectors[lookup[int(k//3)],k%3]=v
        n=vectors[np.argmax(np.linalg.norm(vectors,axis=1))];n=n/np.linalg.norm(n)
        axis=np.eye(3)[np.argmin(abs(n))];t1=np.cross(n,axis);t1/=np.linalg.norm(t1);t2=np.cross(n,t1)
        coeff=vectors@n
        if np.max(abs(vectors-coeff[:,None]*n))>1e-9:raise ValueError('Contact row has inconsistent normals')
        for q,t in enumerate((t1,t2)):
            for node,c in zip(nodes,coeff):
                rows.extend([2*row+q]*3);cols.extend([3*node,3*node+1,3*node+2]);values.extend(c*t)
    return coo_matrix((values,(rows,cols)),shape=(2*C.shape[0],C.shape[1])).tocsr()


def disk_minimum(H,b,radius):
    if radius<=0:return np.zeros(2)
    unconstrained=np.linalg.solve(H,b)
    if np.linalg.norm(unconstrained)<=radius:return unconstrained
    lo=0.;hi=max(float(np.linalg.norm(b)/radius),1e-30)
    for _ in range(45):
        middle=(lo+hi)*.5;z=np.linalg.solve(H+middle*np.eye(2),b)
        if np.linalg.norm(z)>radius:lo=middle
        else:hi=middle
    return np.linalg.solve(H+hi*np.eye(2),b)


@njit(cache=True)
def _disk(a,b,d,x,y,r):
    if r<=0:return 0.,0.
    det=a*d-b*b;u=(d*x-b*y)/det;v=(a*y-b*x)/det
    if u*u+v*v<=r*r:return u,v
    lo=0.;hi=max(np.sqrt(x*x+y*y)/r,1e-30)
    for _ in range(45):
        m=(lo+hi)*.5;aa=a+m;dd=d+m;det=aa*dd-b*b
        u=(dd*x-b*y)/det;v=(aa*y-b*x)/det
        if u*u+v*v>r*r:lo=m
        else:hi=m
    aa=a+hi;dd=d+hi;det=aa*dd-b*b
    return (dd*x-b*y)/det,(aa*y-b*x)/det


@njit(cache=True)
def _sweeps(H,mu,impulse,gradient,steps):
    """Same block coordinate iteration, without millions of Python 2x2 solves."""
    count=len(mu);size=len(impulse)
    for _ in range(steps):
        for i in range(count):
            n=3*i;new=max(0.,impulse[n]+gradient[n]/H[n,n]);delta=new-impulse[n];impulse[n]=new
            if delta!=0:
                for j in range(size):gradient[j]-=H[j,n]*delta
            p=n+1;q=n+2;old0=impulse[p];old1=impulse[q];r=mu[i]*impulse[n]
            if r>0 or old0!=0 or old1!=0:
                x=gradient[p]+H[p,p]*old0+H[p,q]*old1;y=gradient[q]+H[q,p]*old0+H[q,q]*old1
                u,v=_disk(H[p,p],H[p,q],H[q,q],x,y,r)
                impulse[p]=u;impulse[q]=v
                for j in range(size):gradient[j]-=H[j,p]*(u-old0)+H[j,q]*(v-old1)
    error=0.
    for i in range(count):
        n=3*i;error=max(error,abs(impulse[n]-max(0.,impulse[n]+gradient[n]/H[n,n]))*H[n,n])
        if mu[i]>0:
            p=n+1;q=n+2;x=gradient[p]+H[p,p]*impulse[p]+H[p,q]*impulse[q];y=gradient[q]+H[q,p]*impulse[p]+H[q,q]*impulse[q]
            u,v=_disk(H[p,p],H[p,q],H[q,q],x,y,mu[i]*impulse[n])
            a=H[p,p]*(u-impulse[p])+H[p,q]*(v-impulse[q]);b=H[q,p]*(u-impulse[p])+H[q,q]*(v-impulse[q])
            error=max(error,np.sqrt(a*a+b*b))
    return error


def contact(A,rhs,S,C,compliance,offset=None,friction=None,tangent_offset=None,deadline=None,initial_impulse=None):
    Ar=(S.T@A@S).tocsc();br=S.T@rhs;Cn=(C@S).tocsr();count=C.shape[0]
    if count>700:raise RuntimeError('Dense friction proof exceeds 700 contacts; sparse scaling not validated')
    offset=np.zeros(count) if offset is None else np.asarray(offset)
    mu=np.broadcast_to(np.asarray(friction if friction is not None else 0.),(count,))
    if np.any(mu<0):raise ValueError('Negative friction')
    T=tangent_rows(C,mu>0);Ct=(T@S).tocsr()
    # Interleave normal and two tangential directions per contact.
    from scipy.sparse import vstack
    stacked=vstack([Cn,Ct],format='csr');order=np.array([[i,count+2*i,count+2*i+1] for i in range(count)]).ravel()
    J=stacked[order]
    from lava_mpm_cuda_contact27 import try_response
    gpu=try_response(Ar,br,J);factor=None;scaled=None
    if gpu is not None:
        free=gpu.free;H=gpu.H;solve=gpu.solve
    else:
        scale=1/np.sqrt(np.maximum(Ar.diagonal(),1e-30));D=diags(scale)
        scaled=(D@Ar@D).tocsc();scaled.eliminate_zeros()
        factor=splu(scaled,permc_spec='MMD_AT_PLUS_A',diag_pivot_thresh=0.,options={'SymmetricMode':True})
        def solve(b):
            sc=scale if b.ndim==1 else scale[:,None];z=sc*factor.solve(sc*b)
            for _ in range(2):z+=sc*factor.solve(sc*(b-Ar@z))
            return z
        free=solve(br);H=np.empty((J.shape[0],J.shape[0]))
    # Form the small contact response in bounded batches. Keeping the full
    # node-by-contact inverse response plus several refinement temporaries
    # caused memory spikes even for a modest number of actual contacts.
    for begin in range(0,J.shape[0],16) if gpu is None else ():
        if deadline is not None and time.monotonic()>deadline:raise TimeoutError('CPU contact response deadline reached')
        end=min(begin+16,J.shape[0]);H[:,begin:end]=J@solve(J[begin:end].T.toarray())
    H=(H+H.T)*.5
    q=np.asarray(J@free);q[0::3]+=offset
    tangent_offset=np.zeros(2*count) if tangent_offset is None else np.asarray(tangent_offset)
    q.reshape(-1,3)[:,1:]+=tangent_offset.reshape(-1,2)
    epsilon=float(np.max(H.diagonal(),initial=0))*1e-13
    eps=np.full(3*count,max(epsilon,1e-30));eps[0::3]=np.maximum(np.broadcast_to(np.asarray(compliance),(count,)),epsilon)
    H+=np.diag(eps)
    impulse=np.zeros(len(H)) if initial_impulse is None else np.asarray(initial_impulse).copy()
    if impulse.shape!=(len(H),):raise ValueError('Contact initial guess shape mismatch')
    impulse.reshape(-1,3)[:,0]=np.maximum(0,impulse.reshape(-1,3)[:,0])
    gradient=q-H@impulse;last_error=float('inf')
    history_g=[];history_r=[];accelerated=0
    accelerate=os.environ.get('LAVA_MPM_CONTACT_ACCELERATION','none')=='anderson'
    for iteration in range(0,20000,5):
        if deadline is not None and time.monotonic()>deadline:raise TimeoutError('CPU friction deadline reached')
        before=impulse.copy() if accelerate else None
        last_error=_sweeps(H,mu,impulse,gradient,5)
        if last_error<2e-8:break
        if accelerate:
            # Accelerate the SAME block Coulomb fixed point. A candidate is
            # feasible and accepted only if its original natural residual
            # decreases. No contact tolerance or constitutive law changes.
            history_g.append(impulse.copy());history_r.append(impulse-before)
            history_g=history_g[-6:];history_r=history_r[-6:]
            if len(history_r)>1:
                R=np.column_stack([b-a for a,b in zip(history_r[:-1],history_r[1:])])
                G=np.column_stack([b-a for a,b in zip(history_g[:-1],history_g[1:])])
                coeff=np.linalg.lstsq(R,history_r[-1],rcond=1e-10)[0]
                if np.linalg.norm(coeff)<100:
                    candidate=impulse-G@coeff;blocks=candidate.reshape(-1,3)
                    blocks[:,0]=np.maximum(blocks[:,0],0)
                    norm=np.linalg.norm(blocks[:,1:],axis=1)
                    blocks[:,1:]*=np.minimum(1,mu*blocks[:,0]/np.maximum(norm,1e-300))[:,None]
                    candidate_gradient=q-H@candidate
                    error=_sweeps(H,mu,candidate,candidate_gradient,0)
                    if error<last_error:
                        impulse=candidate;gradient=candidate_gradient;last_error=error;accelerated+=1
                        if error<2e-8:break
    else:raise RuntimeError(('Implicit friction did not converge',last_error))
    z=solve(br-J.T@impulse);del factor,scaled
    lam=impulse[0::3];jt=impulse.reshape(-1,3)[:,1:].ravel()
    stationarity=float(np.linalg.norm(Ar@z+J.T@impulse-br)/max(np.linalg.norm(br),1e-30))
    if stationarity>1e-5:raise RuntimeError(('Friction stationarity failed',stationarity))
    tangent_velocity=(np.asarray(T@(S@z))+tangent_offset).reshape(-1,2)
    slip_work=float(np.sum(jt.reshape(-1,2)*tangent_velocity))
    if slip_work < -1e-10:raise RuntimeError(('Friction added energy',slip_work))
    report=dict(iterations=iteration+5,naturalResidual=last_error,stationarity=stationarity,
                slidingDissipationJ=max(0.,slip_work),maximumConeViolation=float(np.max(np.linalg.norm(jt.reshape(-1,2),axis=1)-mu*lam,initial=0)),acceptedAccelerationSteps=accelerated)
    delta=free-z;loss=max(0.,float(.5*delta@(Ar@delta)))
    return S@z,stationarity,lam,loss,iteration+5,T,jt,report


def mixed_contact(A,rhs,S,C,compliance,offset,friction,tangent_offset,physical_rows,deadline=None):
    """Eliminate active fluid pressure cells before the small friction solve.

    Pressure rows have no tangent cone. Including them in the dense Coulomb
    response created three dense directions for every fluid cell, even when
    only a handful of solid points touched the bed. The active-set closure
    below solves the same equations and checks their original residual.
    """
    if os.environ.get('LAVA_MPM_ACTIVE_FRICTION')=='1':
        from lava_mpm_active_contact33 import mixed_contact as active_contact
        return active_contact(A,rhs,S,C,compliance,offset,friction,tangent_offset,physical_rows,deadline)
    from lava_mpm_sparse_pressure import contact as normal_contact
    from scipy.sparse import coo_matrix
    comp=np.broadcast_to(np.asarray(compliance),(C.shape[0],));mu=np.asarray(friction)
    friction_ids=np.flatnonzero(mu>0);normal_ids=np.flatnonzero(mu==0)
    Cp=C[normal_ids];op=np.asarray(offset)[normal_ids];ep=comp[normal_ids]
    key=(A.shape,S.shape,C.shape,len(friction_ids),len(normal_ids))
    saved=_PRESSURE_GUESS.get(key) if os.environ.get('LAVA_MPM_CONTACT_WARM_START')=='1' else None
    cached=None
    if saved is not None and np.linalg.norm(rhs-saved[1])<.2*max(np.linalg.norm(saved[1]),1e-20) and np.linalg.norm(np.asarray(offset)-saved[2])<.2*max(np.linalg.norm(saved[2]),1e-8):cached=saved[0]
    normal=normal_contact(A,rhs,S,C,comp,offset,deadline=deadline) if cached is None else None
    if normal is not None and not np.any(normal[2][friction_ids]>0):
        # With every frictional normal inactive, all Coulomb disks have
        # radius zero. The normal solution is already the exact mixed
        # solution, including any active frictionless pressure constraints.
        T=tangent_rows(C,mu>0);jt=np.zeros(T.shape[0])
        report=dict(iterations=normal[4],naturalResidual=normal[1],stationarity=normal[1],slidingDissipationJ=0.,maximumConeViolation=0.,pressureActiveIterations=0,condensedNormalRows=len(ep),frictionRows=len(friction_ids),physicalRows=physical_rows,unloadedFrictionFastPath=True)
        return (*normal,T,jt,report)
    active=(np.asarray(Cp@normal[0]).ravel()+op>0) if cached is None else cached.copy()
    initial_impulse=np.zeros((len(friction_ids),3))
    if normal is not None:initial_impulse[:,0]=normal[2][friction_ids]
    elif saved is not None:initial_impulse[:]=saved[3]
    previous=None
    for outer in range(32):
        if deadline is not None and time.monotonic()>deadline:raise TimeoutError('CPU mixed contact deadline reached')
        Ca=Cp[active];inv=1/ep[active]
        condensed=A+Ca.T@diags(inv)@Ca;load=rhs-Ca.T@(op[active]*inv)
        tangent_small=np.asarray(tangent_offset).reshape(-1,2)[friction_ids].ravel()
        result=contact(condensed,load,S,C[friction_ids],comp[friction_ids],np.asarray(offset)[friction_ids],mu[friction_ids],tangent_small,deadline,initial_impulse.ravel())
        initial_impulse[:,0]=result[2];initial_impulse[:,1:]=result[6].reshape(-1,2)
        u=result[0];q=np.asarray(Cp@u).ravel()+op;updated=q>0
        pressure=np.maximum(q,0)/ep
        lam=np.zeros(C.shape[0]);lam[friction_ids]=result[2];lam[normal_ids]=pressure
        small_T=result[5].tocoo();rows=2*friction_ids[small_T.row//2]+small_T.row%2
        T=coo_matrix((small_T.data,(rows,small_T.col)),shape=(2*C.shape[0],C.shape[1])).tocsr()
        jt=np.zeros(2*C.shape[0]);jt.reshape(-1,2)[friction_ids]=result[6].reshape(-1,2)
        balance=np.asarray(S.T@(A@u+C.T@lam+T.T@jt-rhs)).ravel()
        scale=max(np.linalg.norm(S.T@rhs),np.linalg.norm(S.T@(C.T@lam)),1e-20)
        residual=float(np.linalg.norm(balance)/scale)
        if np.array_equal(updated,active) and residual<1e-5:
            if os.environ.get('LAVA_MPM_CONTACT_WARM_START')=='1':
                _PRESSURE_GUESS.clear();_PRESSURE_GUESS[key]=(updated.copy(),rhs.copy(),np.asarray(offset).copy(),initial_impulse.copy())
            report=dict(result[7],stationarity=residual,pressureActiveIterations=outer+1,condensedNormalRows=len(ep),frictionRows=len(friction_ids),physicalRows=physical_rows)
            # The objective loss is diagnostic, not injected as contact heat.
            loss=result[3]+float(np.sum(ep*pressure*pressure))
            return u,residual,lam,loss,result[4],T,jt,report
        if previous is not None and np.array_equal(updated,previous):
            if cached is not None:
                _PRESSURE_GUESS.clear()
                return mixed_contact(A,rhs,S,C,compliance,offset,friction,tangent_offset,physical_rows,deadline)
            raise RuntimeError(('Mixed contact pressure active set cycled',residual))
        previous=active.copy();active=updated
    raise RuntimeError(('Mixed contact did not converge',residual))
