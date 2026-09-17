"""Prescribed laboratory grip velocities, composed with existing boundaries."""
import numpy as np


def prescribe(S,lift,mask,values):
    S=S.tocsr();mask=np.asarray(mask).ravel();values=np.asarray(values).ravel()
    fixed={}
    for row in np.flatnonzero(mask):
        lo,hi=S.indptr[row:row+2]
        if hi==lo:
            if abs(values[row]-lift[row])>1e-12:raise ValueError('Conflicting prescribed boundary velocities')
            continue
        if hi-lo!=1:raise ValueError('Grip constraint requires a single reflected degree of freedom')
        col=int(S.indices[lo]);val=(values[row]-lift[row])/S.data[lo]
        if col in fixed and abs(fixed[col]-val)>1e-12:raise ValueError('Conflicting reflected grip velocities')
        fixed[col]=val
    prescribed=np.zeros(S.shape[1]);free=np.ones(S.shape[1],dtype=bool)
    for col,val in fixed.items():prescribed[col]=val;free[col]=False
    return S[:,free],lift+S@prescribed


def extension_grips(half_length,zmin,speed):
    """Upper specimen end grips; other degrees of freedom stay unconstrained.

    A physical displacement boundary for the fracture validation coupon.
    This is never applied to the free lava shot or used to paint a crack.
    """
    def constraint(xyz):
        mask=np.zeros_like(xyz,dtype=bool);values=np.zeros_like(xyz)
        mask[:,0]=(abs(xyz[:,0])>=half_length)&(xyz[:,2]>=zmin)
        values[:,0]=np.sign(xyz[:,0])*speed
        return mask,values
    return constraint
