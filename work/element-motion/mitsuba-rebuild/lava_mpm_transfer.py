"""Affine impulse transfer with a declared, timestep-scaled APIC filter.

An experimental alternative to repeated full APIC remapping. The zero-time
map is identity, and force-free filtering has a fixed physical-time rate.
It can retain FLIP null modes; trajectory/energy tests are required before use.
"""
import numpy as np


def transfer(v,C,before,after,local,w,dp,cell,dt,filter_seconds=.001):
    if filter_seconds<=0 or dt<0:raise ValueError('Invalid transfer timestep/filter time')
    interpolate=lambda u:np.sum(w[:,:,None]*u[local],axis=1)
    affine=lambda u:4*np.einsum('pk,pki,pkj->pij',w,u[local],dp)/np.asarray(cell)[None,None,:]**2
    delta=after-before
    impulse_v=v+interpolate(delta);impulse_C=C+affine(delta)
    blend=-np.expm1(-dt/filter_seconds)
    return (1-blend)*impulse_v+blend*interpolate(after),(1-blend)*impulse_C+blend*affine(after)
