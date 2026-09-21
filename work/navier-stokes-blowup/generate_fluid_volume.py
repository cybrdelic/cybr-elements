#!/usr/bin/env python3
"""Generate an actual advected incompressible fluid tracer volume.

This does NOT draw streamlines.  It solves the passive-scalar transport equation

    d rho / dt + u . grad(rho) = 0

by backward characteristic tracing through the time-dependent smooth
axisymmetric divergence-free similarity velocity field used by the CYBR
Navier-Stokes visualization.

The visible scalar is dye concentration carried by the fluid.  The fluid
itself is incompressible and occupies the domain; the dye makes its motion
visible.  The velocity field matches the leading shrinking-core time exponents
but is not the exact E/U/Pi + annular-pulse + forcing construction from the
OpenAI proof.
"""
from __future__ import annotations
import argparse
import json
import math
import struct
from pathlib import Path
import numpy as np


def parse_args():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=Path("rendered/navier-stokes-fluid"))
    p.add_argument("--frames", type=int, default=8)
    p.add_argument("--grid", type=int, default=96)
    p.add_argument("--tau-max", type=float, default=0.28)
    p.add_argument("--tau-min", type=float, default=0.008)
    p.add_argument("--h", type=float, default=0.009)
    p.add_argument("--extent", type=float, default=1.18)
    p.add_argument("--char-step", type=float, default=0.075,
                   help="maximum step in logarithmic time s=-log(tau)")
    return p.parse_args()


def scales(tau: float, h: float):
    return tau**0.5, tau**(0.5-h), tau**(-0.5-h)


def velocity(x,y,z,tau,h):
    """Physical velocity components of the smooth divergence-free surrogate."""
    lr,lz,ut_scale=scales(tau,h)
    r=np.sqrt(x*x+y*y)
    R=r/lr
    Z=z/lz
    env=np.exp(-0.5*(R*R+0.72*Z*Z))
    C=0.62
    swirl=2.15

    ur=-(C/tau)*r*(1.0-0.72*Z*Z)*env
    uz=(C/tau)*z*(2.0-R*R)*env
    ut=swirl*ut_scale*R*env*(1.0+0.08*np.tanh(Z))

    invr=np.where(r>1e-12,1.0/r,0.0)
    c=np.where(r>1e-12,x*invr,1.0)
    s=np.where(r>1e-12,y*invr,0.0)
    ux=ur*c-ut*s
    uy=ur*s+ut*c
    return ux,uy,uz


def initial_dye(x,y,z,tau0,h):
    """Smooth, structured dye distribution embedded in the initial fluid."""
    lr,lz,_=scales(tau0,h)
    r=np.sqrt(x*x+y*y)
    R=r/lr
    Z=z/lz
    th=np.arctan2(y,x)

    # Two interleaved material sheets and a weaker central marker.  These are
    # passive dye concentrations, not velocity-field geometry.
    z1=0.46*np.sin(th+0.55)+0.10*np.sin(3*th)
    r1=0.78+0.10*np.cos(2*th-0.3)
    a=np.exp(-((R-r1)/0.16)**2-((Z-z1)/0.18)**2)

    z2=-0.42*np.sin(2*th-0.25)
    r2=1.03+0.08*np.sin(3*th+0.8)
    b=np.exp(-((R-r2)/0.14)**2-((Z-z2)/0.16)**2)

    ribbon=np.exp(-((R-0.56)/0.13)**2-(Z/0.42)**2)
    ribbon*=0.35+0.65*(0.5+0.5*np.cos(5*th+2.4*Z))**2

    core=0.17*np.exp(-1.8*(R*R+0.82*Z*Z))
    rho=0.72*a+0.56*b+0.48*ribbon+core
    return np.clip(rho,0.0,1.0).astype(np.float32)


def backtrace_to_initial(x,y,z,tau_final,tau0,h,max_ds):
    """RK2 backward characteristics in s=-log(tau).

    dx/ds = tau * u(x,tau), because dt/ds=tau.  This removes the stiffness
    associated with |u| growing as tau approaches zero.
    """
    if abs(tau_final-tau0)<1e-14:
        return x,y,z,0
    s0=-math.log(tau0)
    sf=-math.log(tau_final)
    n=max(1,int(math.ceil(abs(sf-s0)/max_ds)))
    ds=(s0-sf)/n

    px=x.astype(np.float32,copy=True)
    py=y.astype(np.float32,copy=True)
    pz=z.astype(np.float32,copy=True)
    s=sf
    for _ in range(n):
        tau=math.exp(-s)
        ux,uy,uz=velocity(px,py,pz,tau,h)
        kx=(tau*ux).astype(np.float32)
        ky=(tau*uy).astype(np.float32)
        kz=(tau*uz).astype(np.float32)

        sm=s+0.5*ds
        taum=math.exp(-sm)
        mx=px+np.float32(0.5*ds)*kx
        my=py+np.float32(0.5*ds)*ky
        mz=pz+np.float32(0.5*ds)*kz
        ux,uy,uz=velocity(mx,my,mz,taum,h)
        px += np.float32(ds*taum)*ux.astype(np.float32)
        py += np.float32(ds*taum)*uy.astype(np.float32)
        pz += np.float32(ds*taum)*uz.astype(np.float32)
        s += ds
    return px,py,pz,n


def write_cgrid(path,nx,ny,nz,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    arr=np.asarray(data,dtype="<f4")
    if arr.shape!=(nz,ny,nx):
        raise ValueError((arr.shape,(nz,ny,nx)))
    if not np.isfinite(arr).all() or arr.min()<0 or arr.max()>1.000001:
        raise ValueError("invalid density")
    with path.open("wb") as f:
        f.write(struct.pack("<3i",nx,ny,nz))
        f.write(arr.tobytes(order="C"))


def main():
    a=parse_args()
    if not (0<a.tau_min<a.tau_max<1):
        raise ValueError("require 0 < tau_min < tau_max < 1")
    if not (0<a.h<0.01):
        raise ValueError("require 0 < h < 0.01")
    if a.grid<48:
        raise ValueError("grid must be >= 48")

    out=a.out.resolve()
    vol=out/"volumes"
    vol.mkdir(parents=True,exist_ok=True)

    n=a.grid
    e=a.extent
    # Cell-centered fixed world grid.  The fluid is not artificially rescaled
    # between frames.
    coords=np.linspace(-e,e,n,dtype=np.float32)
    zz,yy,xx=np.meshgrid(coords,coords,coords,indexing="ij")
    dx=float(coords[1]-coords[0])
    voxel=dx**3

    taus=np.geomspace(a.tau_max,a.tau_min,a.frames)
    rows=[]
    initial_mass=None
    for i,tau in enumerate(taus):
        x0,y0,z0,steps=backtrace_to_initial(xx,yy,zz,float(tau),a.tau_max,a.h,a.char_step)
        rho=initial_dye(x0,y0,z0,a.tau_max,a.h)

        # Suppress only numerically insignificant tails to keep delta tracking
        # efficient.  No per-frame normalization is performed.
        rho=np.where(rho<1e-4,0.0,rho).astype(np.float32)
        file=vol/f"fluid_{i:04d}.cgrid"
        write_cgrid(file,n,n,n,rho)

        ux,uy,uz=velocity(xx,yy,zz,float(tau),a.h)
        speed2=ux*ux+uy*uy+uz*uz
        vmax=float(np.sqrt(np.max(speed2)))
        energy=float(0.5*np.sum(speed2,dtype=np.float64)*voxel)
        mass=float(np.sum(rho,dtype=np.float64)*voxel)
        if initial_mass is None:
            initial_mass=mass

        lr,lz,uchar=scales(float(tau),a.h)
        row={
            "frame":i,
            "tau":float(tau),
            "t":float(1.0-tau),
            "grid":str(file.relative_to(out)),
            "bounds":[[-e,-e,-e],[e,e,e]],
            "gridResolution":[n,n,n],
            "characteristicSteps":steps,
            "radialCoreScale":lr,
            "axialCoreScale":lz,
            "characteristicVelocity":uchar,
            "gridMaxSpeed":vmax,
            "gridEnergy":energy,
            "dyeMass":mass,
            "dyeMassRelative":mass/initial_mass,
            "densityMax":float(rho.max()),
            "densityMean":float(rho.mean()),
        }
        rows.append(row)
        print(json.dumps(row),flush=True)
        del x0,y0,z0,rho,ux,uy,uz,speed2

    config={
        "kind":"advected incompressible fluid dye",
        "equation":"d rho/dt + u dot grad(rho) = 0",
        "transport":"RK2 backward characteristics in logarithmic time s=-log(tau)",
        "velocity":"smooth axisymmetric divergence-free similarity surrogate",
        "fixedWorldGrid":True,
        "frames":a.frames,
        "grid":n,
        "tauMax":a.tau_max,
        "tauMin":a.tau_min,
        "h":a.h,
        "worldExtent":a.extent,
        "noImageGeneration":True,
        "disclosure":(
            "The visible volume is passive dye carried by the incompressible fluid. "
            "The velocity matches the leading shrinking-core exponents but is not the "
            "paper's exact full E/U/Pi, annular-pulse, pressure and forcing construction."
        ),
    }
    (out/"config.json").write_text(json.dumps(config,indent=2))
    (out/"metrics.json").write_text(json.dumps(rows,indent=2))


if __name__=="__main__":
    main()
