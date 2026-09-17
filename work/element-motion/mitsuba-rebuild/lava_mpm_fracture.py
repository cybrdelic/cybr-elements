"""Phase-created connectivity and multiple material velocity fields.

Edges carry topology only; the MPM constitutive law carries stress and fracture
work. Broken material components receive independent velocity degrees of
freedom, with pairwise unilateral contact and equal/opposite impulses.
"""
import os
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse import bmat,diags
from scipy.sparse.linalg import spsolve,splu
from scipy.optimize import nnls
from scipy.linalg import solve_triangular
from scipy.sparse.csgraph import connected_components
from numba import njit


class Connectivity:
    def __init__(self,n):
        self.frozen=np.zeros(n,dtype=bool);self.edges=np.empty((0,2),dtype=int);self.broken=np.zeros(0,dtype=bool)
        self.labels=np.zeros(n,dtype=int)

    def update(self,x,solid,damage,directions,spacing,threshold=.85):
        cold=solid>threshold;new=cold&~self.frozen
        if new.any():
            active=np.flatnonzero(cold);pairs=cKDTree(x[active]/spacing).query_pairs(1.82,output_type='ndarray')
            pairs=active[pairs];pairs=pairs[new[pairs].any(1)]
            if len(pairs):
                if len(self.edges):
                    keep=~new[self.edges].any(1);self.edges=self.edges[keep];self.broken=self.broken[keep]
                self.edges=np.r_[self.edges,pairs];self.broken=np.r_[self.broken,np.zeros(len(pairs),dtype=bool)]
                self.edges,ix=np.unique(np.sort(self.edges,axis=1),axis=0,return_index=True);self.broken=self.broken[ix]
        self.frozen=cold
        if len(self.edges):
            a,b=self.edges.T;d=x[b]-x[a];d/=np.maximum(np.linalg.norm(d,axis=1)[:,None],1e-30)
            # A failed tensile band loses bonds crossing its principal plane.
            # There is no time schedule, seeded fracture map, or mesh cut.
            # A fully failed quadrature point cannot remain a bridge merely
            # because its neighbour is intact. An AT2 crack decays away from
            # its centre (approximately exp(-distance/ell)); averaging the
            # two endpoints suppressed precisely those resolved crack tips.
            # Use the normal belonging to the failed endpoint, not the
            # possibly unrelated normal of its intact neighbour.
            failed=((damage[a]>.995)&(abs(np.sum(d*directions[a],axis=1))>.55))|((damage[b]>.995)&(abs(np.sum(d*directions[b],axis=1))>.55))
            self.broken|=failed|~cold[a]|~cold[b]
            intact=~self.broken&cold[a]&cold[b]
            adj=coo_matrix((np.ones(intact.sum()),(a[intact],b[intact])),shape=(len(x),len(x))).tocsr()
            _,labels=connected_components(adj,directed=False)
            self.labels=np.where(cold,labels+1,0)
            # All melt uses one field. Solid clusters are independently
            # advected, and interact with the melt via contact impulses.
            _,self.labels=np.unique(self.labels,return_inverse=True)
        else:
            # An isolated newly coherent point is still a solid field. The
            # absence of edges must not merge it back into the liquid.
            labels=np.where(cold,np.arange(len(x))+1,0)
            _,self.labels=np.unique(labels,return_inverse=True)
        return self.labels


def mechanical_fields(ids,labels):
    tags=np.repeat(labels,ids.shape[1]) if labels.ndim==1 else labels.ravel()
    keys=np.c_[ids.ravel(),tags]
    unique,inverse=np.unique(keys,axis=0,return_inverse=True)
    return unique[:,0],unique[:,1],inverse.reshape(ids.shape)


@njit(cache=True)
def _support_components(sorted_ids,sorted_particles,starts,adj_offsets,adjacent,cold,n):
    result=np.empty(len(sorted_ids),np.int64);mark=np.full(n,-1,np.int64);parent=np.empty(n,np.int64)
    for g in range(len(starts)-1):
        lo=starts[g];hi=starts[g+1];melt=-1
        for j in range(lo,hi):
            p=sorted_particles[j];mark[p]=g;parent[p]=p
            if not cold[p]:
                if melt<0:melt=p
                parent[p]=melt
        for j in range(lo,hi):
            p=sorted_particles[j]
            if not cold[p]:continue
            for a in range(adj_offsets[p],adj_offsets[p+1]):
                q=adjacent[a]
                if mark[q]!=g or not cold[q]:continue
                r=p;s=q
                while parent[r]!=r:r=parent[r]
                while parent[s]!=s:s=parent[s]
                if r<s:parent[s]=r
                else:parent[r]=s
        for j in range(lo,hi):
            p=sorted_particles[j];r=p
            while parent[r]!=r:r=parent[r]
            result[j]=r+1 if cold[p] else 0
    return result


def local_fracture_labels(ids,network,shape,origin,dx,ground=True,cell_size=None,inlet_plane=None):
    """Enrich each grid stencil, not just completely detached global pieces.

    A crack can cross a grid stencil while its tip remains connected farther
    away. Global connected-component labels incorrectly weld such a crack.
    Connectivity here is restricted to the actual particles in each support.
    """
    n=len(ids);a,b=network.edges[~network.broken].T
    adj=coo_matrix((np.ones(2*len(a)),(np.r_[a,b],np.r_[b,a])),shape=(n,n)).tocsr()
    order=np.argsort(ids.ravel(),kind='stable');sid=ids.ravel()[order];particles=(order//27).astype('int64')
    starts=np.r_[0,np.flatnonzero(np.diff(sid))+1,len(sid)]
    roots=_support_components(sid,particles,starts,adj.indptr,adj.indices,network.frozen,n)
    tags=np.empty_like(ids);tags.ravel()[order]=roots
    # A negative-z ghost must share its reflected node's component name,
    # including when the reflected support includes additional particles.
    cell=np.full(3,dx) if cell_size is None else np.asarray(cell_size)
    coordinates=np.array(np.unravel_index(ids.ravel(),shape)).T.reshape(*ids.shape,3)
    xyz=np.asarray(origin)+coordinates*cell
    reflected=xyz.copy();ghost=np.zeros(ids.shape,dtype=bool)
    if ground:
        zghost=xyz[:,:,2]<-cell[2]*1e-7
        reflected[:,:,2]=np.where(zghost,-xyz[:,:,2],xyz[:,:,2]);ghost|=zghost
    if inlet_plane is not None:
        xghost=xyz[:,:,0]<inlet_plane-cell[0]*1e-7
        reflected[:,:,0]=np.where(xghost,2*inlet_plane-xyz[:,:,0],xyz[:,:,0]);ghost|=xghost
    pp,kk=np.nonzero(ghost)
    if len(pp):
        mirrored=np.rint((reflected[pp,kk]-origin)/cell).astype(int)
        mirror=np.ravel_multi_index(mirrored.T,shape)
        matches=ids[pp]==mirror[:,None]
        if not matches.any(1).all():raise RuntimeError('Missing reflected particle support')
        tags[pp,kk]=tags[pp,matches.argmax(1)]
    return tags


def contact_matrix(grid_ids,local,grad,mass,gm,dx,rho):
    normals=np.zeros((len(gm),3))
    for axis in range(3):np.add.at(normals[:,axis],local.ravel(),(mass[:,None]*grad[:,:,axis]).ravel())
    starts=np.r_[0,np.flatnonzero(np.diff(grid_ids))+1,len(grid_ids)];rr=[];cc=[];vv=[];pairs=[]
    for lo,hi in zip(starts[:-1],starts[1:]):
        for a in range(lo,hi):
            for b in range(a+1,hi):
                # A vanishing B-spline tail is not a resolved interface.
                # Retain its mass in P2G, but do not constrain a velocity
                # extrapolated from less than 1e-4 cell mass. An absolute
                # kilogram cutoff made this criterion scale dependent.
                if min(gm[a],gm[b])<rho*dx**3*1e-4 or gm[a]+gm[b]<rho*dx**3*.18:continue
                normal=normals[a]/gm[a]-normals[b]/gm[b];norm=np.linalg.norm(normal)
                if norm<1e-9:continue
                normal/=norm;row=len(pairs);pairs.append((a,b))
                for axis in range(3):
                    rr.extend([row,row]);cc.extend([a*3+axis,b*3+axis]);vv.extend([normal[axis],-normal[axis]])
    return coo_matrix((vv,(rr,cc)),shape=(len(pairs),len(gm)*3)).tocsr(),np.array(pairs,dtype=int).reshape(-1,2)


def viscous_interfaces(grid_ids, mass, liquid, viscosity, dx, rho, dt,cell_size=None,field_gradient=None):
    """Conservative diffuse-interface traction between melt and its crust.

    Previously the separate phase fields exchanged normal collision impulses
    only. A cooled grain could therefore slide through viscous melt without
    tangential drag. This finite-volume closure uses a one-cell interface
    thickness; its spatial accuracy still needs a two-phase convergence test.
    Solid/solid friction is a separate, still-unimplemented contact law.
    """
    starts=np.r_[0,np.flatnonzero(np.diff(grid_ids))+1,len(grid_ids)]
    pairs=[];coeff=[];rr=[];cc=[];vv=[]
    for lo,hi in zip(starts[:-1],starts[1:]):
        for a in range(lo,hi):
            for b in range(a+1,hi):
                if not (liquid[a] or liquid[b]) or min(mass[a],mass[b])<1e-15:continue
                eta=viscosity[a] if liquid[a] else viscosity[b]
                if liquid[a] and liquid[b]:eta=2/(1/viscosity[a]+1/viscosity[b])
                length2=dx*dx
                if cell_size is not None and field_gradient is not None:
                    normal=field_gradient[a]/mass[a]-field_gradient[b]/mass[b];norm=np.linalg.norm(normal)
                    if norm>1e-12:normal/=norm;length2=1/np.sum((normal/cell_size)**2)
                conductance=dt*eta*2*min(mass[a],mass[b])/(rho*length2)
                pairs.append((a,b));coeff.append(conductance)
                for c in range(3):
                    ai=3*a+c;bi=3*b+c
                    rr.extend([ai,ai,bi,bi]);cc.extend([ai,bi,ai,bi]);vv.extend([conductance,-conductance,-conductance,conductance])
    matrix=coo_matrix((vv,(rr,cc)),shape=(len(mass)*3,)*2).tocsr()
    return matrix,np.array(pairs,dtype=int).reshape(-1,2),np.array(coeff)


def implicit_contact(A,rhs,S,C,compliance,offset=None):
    """Nonnegative dual contact solve within backward Euler mechanics.

    The small positive compliance regularizes redundant contact constraints.
    Tangential friction is intentionally excluded here until a cone solve is
    validated; post-projecting stiff material velocities is not stable.
    """
    Ar=(S.T@A@S).tocsc();br=S.T@rhs;Cr=(C@S).tocsr()
    # The frozen skeleton and low-mass free-surface nodes span many orders
    # of magnitude. Symmetric equilibration preserves the physical system.
    scale_a=1/np.sqrt(np.maximum(Ar.diagonal(),1e-30))
    Da=diags(scale_a);factor=splu((Da@Ar@Da).tocsc(),permc_spec=os.environ.get('LAVA_CONTACT_ORDER','COLAMD'))
    def solve(b):
        ss=scale_a if b.ndim==1 else scale_a[:,None]
        result=ss*factor.solve(ss*b)
        for _ in range(2):
            error=b-Ar@result
            relative=np.linalg.norm(error,axis=0)/np.maximum(np.linalg.norm(b,axis=0),1e-30)
            if np.max(relative)<1e-7:break
            result+=ss*factor.solve(ss*error)
        return result
    free=solve(br)
    if not C.shape[0]:return S@free,0.,np.zeros(0),0.,0
    offset=np.zeros(C.shape[0]) if offset is None else np.asarray(offset).ravel()
    free_violation=np.asarray(Cr@free).ravel()+offset
    selected=np.flatnonzero(free_violation>1e-12)
    multipliers=np.zeros(C.shape[0]);z=free.copy();effective_compliance=np.broadcast_to(np.asarray(compliance),(C.shape[0],)).copy()
    response=np.empty((Ar.shape[0],0));count=0
    # Build responses only for approaching contacts. Separating contacts are
    # checked against the resulting *coupled* velocity; newly approaching ones
    # are added and the exact restricted dual is resolved. No contacts are
    # silently discarded based on the initial velocity.
    for expansion in range(20):
        if not len(selected):break
        if len(selected)>1400:raise RuntimeError('Active contact proof exceeds the CPU budget')
        response=np.c_[response,solve(Cr[selected[count:]].T.toarray())];count=len(selected)
        H=np.asarray(Cr[selected]@response);H=(H+H.T)*.5
        effective_compliance=np.maximum(np.broadcast_to(np.asarray(compliance),(C.shape[0],)),float(np.max(H.diagonal()))*1e-12);H+=np.diag(effective_compliance[selected])
        scale=1/np.sqrt(np.maximum(H.diagonal(),1e-30));Hs=scale[:,None]*H*scale[None,:];q=scale*free_violation[selected]
        L=np.linalg.cholesky(Hs);target=solve_triangular(L,q,lower=True)
        solution,_=nnls(L.T,target,maxiter=max(100,12*len(H)))
        multipliers[:]=0;multipliers[selected]=scale*solution;z=free-response@multipliers[selected]
        remaining=np.asarray(Cr@z).ravel()+offset;remaining[selected]=-np.inf
        new=np.flatnonzero(remaining>1e-11)
        if not len(new):break
        selected=np.r_[selected,new[np.argsort(remaining[new])[-96:]]]
    else:raise RuntimeError('Contact working set did not close; no step accepted')
    violation=np.asarray(Cr@z).ravel()-effective_compliance*multipliers
    violation+=offset
    if violation.max(initial=0)>1e-6:raise RuntimeError(('Contact complementarity failed',float(violation.max())))
    residual=np.linalg.norm(Ar@z+Cr.T@multipliers-br)/max(np.linalg.norm(br),1e-30)
    if not np.isfinite(z).all() or residual>1e-5:raise RuntimeError(('Implicit contact residual failed',residual))
    delta=free-z
    dissipation=max(0,float(.5*delta@(Ar@delta)+np.sum(effective_compliance*multipliers*multipliers)))
    # This generalized backward-Euler objective loss is reported separately;
    # it is not all injected into heat, since Ar also contains elastic terms.
    return S@z,float(residual),multipliers,dissipation,expansion+1


@njit(cache=True)
def contact_fields(grid_ids,field_ids,local,w,grad,mass,velocity,gm,dx,rho,friction=.6):
    normals=np.zeros_like(velocity)
    for p in range(len(local)):
        for k in range(27):normals[local[p,k]]+=mass[p]*grad[p,k]
    before=np.zeros(3);after=np.zeros(3);count=0;work=0.;heat=np.zeros(len(gm))
    for i in range(len(gm)):before+=gm[i]*velocity[i]
    lo=0
    while lo<len(gm):
        hi=lo+1
        while hi<len(gm) and grid_ids[hi]==grid_ids[lo]:hi+=1
        if hi-lo>1:
            for iteration in range(3):
                for a in range(lo,hi):
                    for b in range(a+1,hi):
                        if min(gm[a],gm[b])<1e-12 or gm[a]+gm[b]<rho*dx**3*.18:continue
                        normal=normals[a]/gm[a]-normals[b]/gm[b];mag=np.sqrt(np.sum(normal**2))
                        if mag<1e-9:continue
                        normal/=mag;relative=velocity[a]-velocity[b];approach=np.dot(relative,normal)
                        if approach<=0:continue
                        inverse=1/gm[a]+1/gm[b];jn=approach/inverse
                        tangent=relative-approach*normal;speed=np.sqrt(np.sum(tangent**2))
                        jt=min(friction*jn,speed/inverse)
                        impulse=normal*jn+tangent*jt/max(speed,1e-30)
                        energy0=.5*(gm[a]*np.sum(velocity[a]**2)+gm[b]*np.sum(velocity[b]**2))
                        velocity[a]-=impulse/gm[a];velocity[b]+=impulse/gm[b]
                        energy1=.5*(gm[a]*np.sum(velocity[a]**2)+gm[b]*np.sum(velocity[b]**2))
                        lost=max(0,energy0-energy1);work+=lost;heat[a]+=lost*.5;heat[b]+=lost*.5;count+=1
        lo=hi
    for i in range(len(gm)):after+=gm[i]*velocity[i]
    return count,work,np.sqrt(np.sum((after-before)**2)),heat
