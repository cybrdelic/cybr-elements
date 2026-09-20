"""Conservative depth-averaged lava flow for the CYBRDELIC glyph mold.

The formation shot is a shallow engraved mold, so resolving the full 3-D
vertical momentum field is wasteful and, at review resolutions, under-resolves
the thin letter channels.  This module instead solves a conservative
depth-averaged free-surface flow over the actual signed-distance cavity.

The state is physical height, bulk temperature, surface-skin temperature, and
thermal/mechanical damage.  Localized inlets add volume and enthalpy.  All
subsequent spreading is pressure-driven through conservative face fluxes; there
is no target morph, no per-cell target force, and no render mask.

The mobility combines a temperature-dependent lubrication term with an
effective basal-slip term used as a grid-scale closure for unresolved near-wall
shear.  A Bingham-like yield factor arrests cooled material.  The surface skin
cools faster near the stone walls and can crack under thermal shock while the
hot bulk remains mobile underneath it.  A conservative overflow safety pass
prevents numerical source cells from exceeding the physical mold depth: excess
volume is redistributed only within the same connected cavity component.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import math
import numpy as np
from scipy.ndimage import label

from .lava_formation import PourFormationConfig, _bilinear, _source_coords


@dataclass(frozen=True)
class ShallowLavaConfig:
    nx: int = 256
    ny: int = 128
    x_min: float = -.70
    x_max: float = .70
    y_min: float = -.34
    y_max: float = .34

    floor: float = .032
    wall_height: float = .052
    target_depth: float = .041
    max_depth: float = .0495

    pour_duration: float = 4.15
    inlet_stagger_seconds: float = 1.35
    source_sigma_min: float = .0040
    source_sigma_max: float = .0080
    source_sigma_clearance_scale: float = .24
    source_longitudinal_stretch: float = 1.7
    source_ramp_seconds: float = .32
    impact_head: float = .020
    impact_sigma_scale: float = 2.2
    impact_longitudinal_stretch: float = 2.8
    impact_forward_shift: float = .012

    feed_temperature: float = 1580.
    feed_skin_temperature: float = 1435.
    mold_temperature: float = 405.

    density: float = 2600.
    gravity: float = 9.81
    viscosity_hot: float = 105.
    viscosity_cold: float = 6.0e5
    basal_slip_length: float = .022
    contact_line_mobility: float = .0085
    max_mobility: float = .020
    front_regularization_depth: float = .0045
    yield_stress_hot: float = 2.0
    yield_stress_cold: float = 950.

    solidus: float = 1250.
    liquidus: float = 1450.
    heat_capacity: float = 1200.
    skin_thickness: float = .0036
    skin_exchange_rate: float = .16
    wall_skin_exchange_rate: float = .32
    wall_cooling_length: float = .012
    skin_reheat_rate: float = 3.2
    bulk_cooling_rate: float = .018
    wall_bulk_cooling_rate: float = .045
    surface_emissivity: float = .90

    # Explicit crust mechanics: surface age is advected with the flow, cooling
    # grows finite crust thickness, and strain can tear that crust open over
    # the still-hot interior.
    crust_thermal_diffusivity: float = 8.0e-7
    crust_max_thickness: float = .0055
    crust_maturity_time: float = .75
    strain_memory_time: float = 2.8
    tear_strain_threshold: float = .55
    tear_growth_rate: float = 1.35
    tear_heal_rate: float = .70
    tear_cooling_gain: float = .28
    tear_sag: float = .00125

    rope_wavelength: float = .019
    rope_amplitude: float = .00185
    billow_wavelength: float = .070
    billow_amplitude: float = .00090

    cfl: float = .20
    max_dt: float = .006
    wet_epsilon: float = .00022

    jet_radius: float = .0027
    jet_visible_height: float = .075
    jet_lean: float = .009
    jet_rings: int = 8
    jet_segments: int = 14
    impact_flare: float = 1.45

    def __post_init__(self):
        if min(self.nx, self.ny) < 32:
            raise ValueError("shallow grid too small")
        if not self.x_max > self.x_min or not self.y_max > self.y_min:
            raise ValueError("invalid shallow domain")
        if not 0 < self.target_depth < self.max_depth < self.wall_height:
            raise ValueError("depths must satisfy target < max < wall")
        if self.pour_duration <= 0 or self.viscosity_hot <= 0:
            raise ValueError("invalid source or viscosity")
        if self.viscosity_cold <= self.viscosity_hot:
            raise ValueError("cold viscosity must exceed hot viscosity")
        if self.liquidus <= self.solidus:
            raise ValueError("invalid phase interval")
        if self.basal_slip_length < 0 or self.contact_line_mobility < 0 or self.max_mobility <= 0:
            raise ValueError("invalid shallow mobility")
        if self.source_ramp_seconds < 0 or self.impact_head < 0 or self.impact_sigma_scale <= 0:
            raise ValueError("invalid inlet impact controls")
        if self.source_longitudinal_stretch < 1 or self.impact_longitudinal_stretch < 1 or self.impact_forward_shift < 0:
            raise ValueError("invalid directional inlet controls")
        if self.jet_lean < 0:
            raise ValueError("invalid jet lean")
        if not 0 < self.cfl <= .25 or self.max_dt <= 0:
            raise ValueError("invalid explicit stability controls")
        if self.jet_rings < 3 or self.jet_segments < 8:
            raise ValueError("jet tessellation too small")
        if self.rope_wavelength <= 0 or self.billow_wavelength <= 0 or self.rope_amplitude < 0 or self.billow_amplitude < 0:
            raise ValueError("invalid pahoehoe surface scales")
        if self.crust_thermal_diffusivity <= 0 or self.crust_max_thickness <= 0 or self.crust_maturity_time <= 0:
            raise ValueError("invalid crust growth controls")
        if self.strain_memory_time <= 0 or self.tear_strain_threshold < 0 or self.tear_growth_rate < 0 or self.tear_heal_rate < 0:
            raise ValueError("invalid crust tear controls")

    @property
    def dx(self):
        return (self.x_max-self.x_min)/(self.nx-1)

    @property
    def dy(self):
        return (self.y_max-self.y_min)/(self.ny-1)

    def manifest(self):
        return asdict(self)


def _smoothstep(x):
    x=np.clip(np.asarray(x,dtype=np.float64),0.,1.)
    return x*x*(3.-2.*x)


def _sample_source_field(field,xx,yy,lo,extent,formation):
    xy=np.stack([xx,yy],axis=-1)
    v,u=_source_coords(xy,lo,extent,field.shape,formation)
    return _bilinear(field,v,u)


def _component_inlets(mask,distance,arrival,xx,yy,formation,tangent_x=None,tangent_y=None):
    labels,count=label(mask)
    components=[]
    for component in range(1,count+1):
        area=int(np.count_nonzero(labels==component))
        if area>=30:
            components.append((component,area))
    components.sort(key=lambda row:-row[1])
    if not components:
        raise RuntimeError("no resolved glyph components in shallow grid")

    rows=[]
    for rank,(component,area) in enumerate(components):
        py,px=np.where(labels==component)
        clearance=distance[py,px]
        deep=clearance>np.percentile(clearance,58)
        py0,px0=py[deep],px[deep]
        count_here=formation.main_nozzles if rank==0 else 1
        quantiles=np.linspace(.07,.93,count_here) if count_here>1 else np.array([.5])
        for q in quantiles:
            target_x=np.quantile(px0,q) if count_here>1 else np.median(px0)
            score=np.abs(px0-target_x)+.16*np.abs(py0-np.median(py0))
            idx=int(np.argmin(score))
            iy,ix=int(py0[idx]),int(px0[idx])
            if tangent_x is None or tangent_y is None:
                tx,ty=1.,0.
            else:
                tx=float(tangent_x[iy,ix]);ty=float(tangent_y[iy,ix])
                length=math.hypot(tx,ty)
                if length<1e-8:tx,ty=1.,0.
                else:tx/=length;ty/=length
            rows.append({
                "component":int(component),
                "areaCells":int(area),
                "ix":ix,"iy":iy,
                "x":float(xx[iy,ix]),"y":float(yy[iy,ix]),
                "tx":float(tx),"ty":float(ty),
                "arrival":float(arrival[iy,ix]),
                "clearance":float(distance[iy,ix]),
            })
    return labels,components,rows


def _inlet_sources(mask,labels,inlets,xx,yy,dx,dy,target_depth,cfg):
    """Partition cavity capacity between physical inlets.

    Each cell in a connected component is assigned to its nearest inlet in that
    component.  The inlet receives exactly that territory's target capacity.
    This avoids the old equal-per-nozzle allocation that overfilled narrow
    territories and underfed wide ones.
    """
    groups={}
    for i,row in enumerate(inlets):
        groups.setdefault(row["component"],[]).append(i)

    territory_cells=np.zeros(len(inlets),np.int64)
    for component,indices in groups.items():
        yy_idx,xx_idx=np.where(labels==component)
        if len(yy_idx)==0:
            continue
        cx=xx[yy_idx,xx_idx]
        cy=yy[yy_idx,xx_idx]
        centers=np.array([[inlets[i]["x"],inlets[i]["y"]] for i in indices],np.float64)
        d2=(cx[:,None]-centers[None,:,0])**2+(cy[:,None]-centers[None,:,1])**2
        owner=np.argmin(d2,axis=1)
        for local,global_index in enumerate(indices):
            territory_cells[global_index]=int(np.count_nonzero(owner==local))

    arrival=np.array([r["arrival"] for r in inlets],np.float64)
    amin=float(arrival.min());amax=float(arrival.max())
    span=max(amax-amin,1e-9)

    sources=[]
    for i,row in enumerate(inlets):
        comp=row["component"]
        cells=max(1,int(territory_cells[i]))
        assigned_volume=cells*dx*dy*target_depth
        start=cfg.inlet_stagger_seconds*(row["arrival"]-amin)/span
        end=start+cfg.pour_duration
        sigma=np.clip(
            row["clearance"]*cfg.source_sigma_clearance_scale,
            cfg.source_sigma_min,cfg.source_sigma_max)
        rx=xx-row["x"];ry=yy-row["y"]
        tx=float(row.get("tx",1.));ty=float(row.get("ty",0.))
        along=rx*tx+ry*ty
        cross=-rx*ty+ry*tx
        source_long=sigma*cfg.source_longitudinal_stretch
        weight=np.exp(-.5*((along/source_long)**2+(cross/sigma)**2))*(labels==comp)
        norm=float(weight.sum()*dx*dy)
        if norm<=0:
            raise RuntimeError("empty inlet support")
        shape=weight/norm
        impact_sigma=sigma*cfg.impact_sigma_scale
        impact_along=impact_sigma*cfg.impact_longitudinal_stretch
        shifted=along-cfg.impact_forward_shift
        impact=np.exp(-.5*((shifted/impact_along)**2+(cross/impact_sigma)**2))*(labels==comp)
        ramp=min(cfg.source_ramp_seconds,cfg.pour_duration*.45)
        envelope_integral=max(cfg.pour_duration-ramp,1e-8)
        sources.append({
            **row,
            "territoryCells":cells,
            "territoryTargetVolumeM3":float(assigned_volume),
            "start":float(start),"end":float(end),
            "assignedVolumeM3":float(assigned_volume),
            "flowRateM3s":float(assigned_volume/envelope_integral),
            "sigma":float(sigma),
            "impactSigma":float(impact_sigma),
            "rampSeconds":float(ramp),
            "shape":shape.astype(np.float64),
            "impact":impact.astype(np.float64),
        })
    return sources


def _phase_fraction(temperature,cfg):
    return _smoothstep(np.clip(
        (temperature-cfg.solidus)/(cfg.liquidus-cfg.solidus),0.,1.))


def _effective_viscosity(bulk,skin,cfg):
    # The bulk dominates depth-averaged flow.  The surface skin contributes
    # drag but cannot freeze a hot interior instantly.
    flow_temperature=.82*bulk+.18*skin
    solid=1.-_phase_fraction(flow_temperature,cfg)
    log_mu=np.log(cfg.viscosity_hot)+(
        np.log(cfg.viscosity_cold)-np.log(cfg.viscosity_hot))*solid
    mu=np.exp(log_mu)
    skin_crust=1.-_phase_fraction(skin,cfg)
    return mu*(1.+2.5*skin_crust**3),flow_temperature


def _axis_flux(h0,h1,bulk0,bulk1,skin0,skin1,head0,head1,valid,delta,cfg):
    hface=.5*(h0+h1)
    bulk=.5*(bulk0+bulk1)
    skin=.5*(skin0+skin1)
    mu,flow_temperature=_effective_viscosity(bulk,skin,cfg)
    melt=_phase_fraction(flow_temperature,cfg)
    crust=1.-melt

    # A small mobility depth regularizes the advancing contact line without
    # adding any precursor-film volume to the conserved height field.
    hm=np.maximum(hface,cfg.front_regularization_depth)
    poisson=cfg.density*cfg.gravity*hm**3/(3.*np.maximum(mu,1e-9))
    slip=cfg.density*cfg.gravity*cfg.basal_slip_length*hm**2/np.maximum(mu,1e-9)
    mobility=(poisson+slip)*(0.04+.96*melt*melt)
    # Grid-scale dynamic-contact-line closure. It acts most strongly on a thin
    # advancing front and vanishes in deep pools, allowing channels to wet
    # without requiring unrealistically tall source mounds.
    front_weight=np.exp(-hface/max(cfg.target_depth*.42,1e-6))
    mobility+=cfg.contact_line_mobility*front_weight*melt*melt

    grad=(head1-head0)/delta
    tau=cfg.density*cfg.gravity*hm*np.abs(grad)
    yield_stress=cfg.yield_stress_hot+(
        cfg.yield_stress_cold-cfg.yield_stress_hot)*crust*crust
    yielded=np.clip(1.-yield_stress/np.maximum(tau,1e-8),0.,1.)
    yielded=yielded*yielded
    mobility=np.minimum(mobility*yielded,cfg.max_mobility)

    q=-mobility*grad
    q*=valid
    return q,mobility


def _face_fluxes(h,bulk,skin,mask,dx,dy,cfg,impact=None):
    head=h if impact is None else h+impact
    qx,kx=_axis_flux(
        h[:,:-1],h[:,1:],bulk[:,:-1],bulk[:,1:],
        skin[:,:-1],skin[:,1:],head[:,:-1],head[:,1:],
        mask[:,:-1]&mask[:,1:],dx,cfg)
    qy,ky=_axis_flux(
        h[:-1,:],h[1:,:],bulk[:-1,:],bulk[1:,:],
        skin[:-1,:],skin[1:,:],head[:-1,:],head[1:,:],
        mask[:-1,:]&mask[1:,:],dy,cfg)
    return qx,qy,float(max(kx.max(initial=0.),ky.max(initial=0.)))


def _cell_velocity_and_strain(qx,qy,h,dx,dy):
    """Recover cell velocity and an invariant depth-averaged strain-rate proxy."""
    u=np.zeros_like(h,np.float64);v=np.zeros_like(h,np.float64)
    if qx.shape[1]:
        u[:,0]=qx[:,0];u[:,-1]=qx[:,-1]
        if h.shape[1]>2:u[:,1:-1]=.5*(qx[:,:-1]+qx[:,1:])
    if qy.shape[0]:
        v[0,:]=qy[0,:];v[-1,:]=qy[-1,:]
        if h.shape[0]>2:v[1:-1,:]=.5*(qy[:-1,:]+qy[1:,:])
    depth=np.maximum(h,1e-5)
    u/=depth;v/=depth
    du_dx=np.gradient(u,dx,axis=1);du_dy=np.gradient(u,dy,axis=0)
    dv_dx=np.gradient(v,dx,axis=1);dv_dy=np.gradient(v,dy,axis=0)
    shear=.5*(du_dy+dv_dx)
    strain=np.sqrt(du_dx*du_dx+dv_dy*dv_dy+2.*shear*shear)
    return u,v,np.nan_to_num(strain,nan=0.,posinf=0.,neginf=0.)


def _advect_scalar_mass(h,scalar,qx,qy,dx,dy,dt):
    fx,fy=_advected_scalar_flux(qx,qy,scalar)
    return h*scalar+dt*_divergence(fx,fy,dx,dy,h.shape)


def _redistribute_overflow_payloads(h,labels,limit,payloads,sweeps=4):
    """Move overflow and all conserved payloads through the same spill path."""
    h=np.asarray(h,np.float64).copy()
    p=np.asarray(payloads,np.float64).copy()
    if p.ndim!=3 or p.shape[1:]!=h.shape:
        raise ValueError("payload stack must have shape (channels, ny, nx)")
    directions=((0,1),(0,-1),(1,0),(-1,0))

    for sweep in range(max(1,int(sweeps))):
        excess=np.maximum(h-limit,0.)
        if float(excess.sum())<=1e-14:break
        frac_excess=np.where(h>1e-12,excess/h,0.)
        excess_p=p*frac_excess[None,:,:]
        h-=excess;p-=excess_p

        capacities=[]
        for dy,dx in directions:
            cap=np.zeros_like(h)
            if dy==0 and dx==1:
                valid=(labels[:,:-1]>0)&(labels[:,:-1]==labels[:,1:])
                cap[:,:-1]=np.where(valid,np.maximum(limit-h[:,1:],0.),0.)
            elif dy==0 and dx==-1:
                valid=(labels[:,1:]>0)&(labels[:,1:]==labels[:,:-1])
                cap[:,1:]=np.where(valid,np.maximum(limit-h[:,:-1],0.),0.)
            elif dy==1:
                valid=(labels[:-1,:]>0)&(labels[:-1,:]==labels[1:,:])
                cap[:-1,:]=np.where(valid,np.maximum(limit-h[1:,:],0.),0.)
            else:
                valid=(labels[1:,:]>0)&(labels[1:,:]==labels[:-1,:])
                cap[1:,:]=np.where(valid,np.maximum(limit-h[:-1,:],0.),0.)
            capacities.append(cap)
        total_cap=np.maximum(sum(capacities),1e-30)
        moved=np.zeros_like(h);moved_p=np.zeros_like(p)
        order=range(4) if sweep%2==0 else range(3,-1,-1)
        for k in order:
            dy,dx=directions[k]
            frac=np.where(total_cap>1e-29,capacities[k]/total_cap,0.)
            send=excess*frac;send_p=excess_p*frac[None,:,:]
            moved+=send;moved_p+=send_p
            if dy==0 and dx==1:
                h[:,1:]+=send[:,:-1];p[:,:,1:]+=send_p[:,:,:-1]
            elif dy==0 and dx==-1:
                h[:,:-1]+=send[:,1:];p[:,:,:-1]+=send_p[:,:,1:]
            elif dy==1:
                h[1:,:]+=send[:-1,:];p[:,1:,:]+=send_p[:,:-1,:]
            else:
                h[:-1,:]+=send[1:,:];p[:,:-1,:]+=send_p[:,1:,:]
        residual=np.maximum(excess-moved,0.)
        ratio=np.where(excess>1e-14,residual/excess,0.)
        h+=residual;p+=excess_p*ratio[None,:,:]

    for component in np.unique(labels):
        if component<=0:continue
        region=labels==component
        hr=h[region];excess=np.maximum(hr-limit,0.);amount=float(excess.sum())
        if amount<=1e-14:continue
        pr=p[:,region]
        fraction=np.where(hr>1e-12,excess/hr,0.)
        excess_p=np.sum(pr*fraction[None,:],axis=1)
        hr=np.minimum(hr,limit);pr-=pr*fraction[None,:]
        capacity=np.maximum(limit-hr,0.);cap=float(capacity.sum())
        moved=min(amount,cap)
        if moved>0:
            add=capacity*(moved/max(cap,1e-30))
            hr+=add
            pr+=add[None,:]*(excess_p/max(amount,1e-30))[:,None]
        residual=amount-moved
        if residual>1e-14:
            k=int(np.argmax(capacity)) if len(capacity) else 0
            hr[k]+=residual
            pr[:,k]+=excess_p*(residual/max(amount,1e-30))
        h[region]=hr;p[:,region]=pr
    return h,p


def _divergence(qx,qy,dx,dy,shape):
    out=np.zeros(shape,np.float64)
    out[:,:-1]-=qx/dx
    out[:,1:]+=qx/dx
    out[:-1,:]-=qy/dy
    out[1:,:]+=qy/dy
    return out


def _advected_scalar_flux(qx,qy,value):
    tx=np.where(qx>=0.,value[:,:-1],value[:,1:])
    ty=np.where(qy>=0.,value[:-1,:],value[1:,:])
    return qx*tx,qy*ty


def _source_envelope(src,t):
    if not src["start"]<=t<src["end"]:
        return 0.
    u=t-src["start"]
    remaining=src["end"]-t
    ramp=float(src.get("rampSeconds",0.))
    if ramp<=1e-12:
        return 1.
    a=_smoothstep(min(1.,u/ramp))
    b=_smoothstep(min(1.,remaining/ramp))
    return float(min(a,b))


def _source_envelope_integral(src,t):
    start,end=float(src["start"]),float(src["end"])
    if t<=start:return 0.
    D=end-start
    u=min(max(t-start,0.),D)
    r=min(float(src.get("rampSeconds",0.)),D*.45)
    if r<=1e-12:return u
    primitive=lambda x:x**3-.5*x**4
    total=D-r
    if u<=r:
        return r*primitive(u/r)
    if u<=D-r:
        return .5*r+(u-r)
    v=(D-u)/r
    return total-r*primitive(v)


def _active_source_fields(t,sources,shape,cfg):
    depth_rate=np.zeros(shape,np.float64)
    heat_rate=np.zeros(shape,np.float64)
    impact=np.zeros(shape,np.float64)
    active=[]
    for i,src in enumerate(sources):
        envelope=_source_envelope(src,t)
        if envelope>0.:
            local=src["flowRateM3s"]*envelope*src["shape"]
            depth_rate+=local
            heat_rate+=local*cfg.feed_temperature
            impact+=cfg.impact_head*envelope*src["impact"]
            active.append(i)
    return depth_rate,heat_rate,impact,active


def _redistribute_overflow(h,labels,limit,energy=None,sweeps=4):
    """Locally spill over-depth fluid while conserving volume and heat.

    The previous pass moved excess across a whole glyph component at once and
    moved height without thermal energy.  This version performs nearest-neighbor
    spill sweeps. Excess depth carries its own energy and can only move through
    cells of the same connected cavity component.

    When energy is omitted, return height only for simple invariant tests.
    With energy supplied, return the pair (height, energy).
    """
    h=np.asarray(h,np.float64).copy()
    scalar_only=energy is None
    e=h.copy() if scalar_only else np.asarray(energy,np.float64).copy()

    directions=((0,1),(0,-1),(1,0),(-1,0))

    for sweep in range(max(1,int(sweeps))):
        excess=np.maximum(h-limit,0.)
        if float(excess.sum())<=1e-14:
            break

        temp=e/np.maximum(h,1e-12)
        excess_e=excess*temp
        h-=excess
        e-=excess_e

        capacities=[]
        for dy,dx in directions:
            cap=np.zeros_like(h)
            if dy==0 and dx==1:
                valid=(labels[:,:-1]>0)&(labels[:,:-1]==labels[:,1:])
                cap[:,:-1]=np.where(valid,np.maximum(limit-h[:,1:],0.),0.)
            elif dy==0 and dx==-1:
                valid=(labels[:,1:]>0)&(labels[:,1:]==labels[:,:-1])
                cap[:,1:]=np.where(valid,np.maximum(limit-h[:,:-1],0.),0.)
            elif dy==1:
                valid=(labels[:-1,:]>0)&(labels[:-1,:]==labels[1:,:])
                cap[:-1,:]=np.where(valid,np.maximum(limit-h[1:,:],0.),0.)
            else:
                valid=(labels[1:,:]>0)&(labels[1:,:]==labels[:-1,:])
                cap[1:,:]=np.where(valid,np.maximum(limit-h[:-1,:],0.),0.)
            capacities.append(cap)

        total_cap=np.maximum(sum(capacities),1e-30)
        moved=np.zeros_like(h)
        moved_e=np.zeros_like(h)

        order=range(4) if sweep%2==0 else range(3,-1,-1)
        for k in order:
            dy,dx=directions[k]
            frac=np.where(total_cap>1e-29,capacities[k]/total_cap,0.)
            send=excess*frac
            send_e=excess_e*frac
            moved+=send
            moved_e+=send_e

            if dy==0 and dx==1:
                h[:,1:]+=send[:,:-1]
                e[:,1:]+=send_e[:,:-1]
            elif dy==0 and dx==-1:
                h[:,:-1]+=send[:,1:]
                e[:,:-1]+=send_e[:,1:]
            elif dy==1:
                h[1:,:]+=send[:-1,:]
                e[1:,:]+=send_e[:-1,:]
            else:
                h[:-1,:]+=send[1:,:]
                e[:-1,:]+=send_e[1:,:]

        h+=np.maximum(excess-moved,0.)
        e+=np.maximum(excess_e-moved_e,0.)

    # A physical mold cannot sustain a free surface above its wall indefinitely.
    # If the finite number of local sweeps leaves a residual, equalize only that
    # over-depth residual within the same connected cavity while carrying its
    # thermal energy.  This is a safety closure, not a target-height morph.
    for component in np.unique(labels):
        if component<=0:
            continue
        region=labels==component
        excess=np.maximum(h[region]-limit,0.)
        amount=float(excess.sum())
        if amount<=1e-14:
            continue
        temp=e[region]/np.maximum(h[region],1e-12)
        excess_energy=float(np.sum(excess*temp))
        hr=np.minimum(h[region],limit)
        er=e[region]-excess*temp
        capacity=np.maximum(limit-hr,0.)
        cap=float(capacity.sum())
        if cap>1e-14:
            moved=min(amount,cap)
            addition=capacity*(moved/cap)
            mix_temperature=excess_energy/max(amount,1e-12)
            hr+=addition
            er+=addition*mix_temperature
            residual=amount-moved
            residual_energy=excess_energy-moved*mix_temperature
        else:
            residual=amount
            residual_energy=excess_energy
        if residual>1e-14:
            # This should only occur if the requested volume exceeds component
            # capacity. Preserve it for diagnostics rather than deleting mass.
            k=int(np.argmax(capacity)) if len(capacity) else 0
            hr[k]+=residual
            er[k]+=residual_energy
        h[region]=hr
        e[region]=er

    return h if scalar_only else (h,e)


def _thermal_update(h,bulk,skin,source_depth,dt,mask,wall_factor,cfg,flow_activity):
    wet=h>cfg.wet_epsilon
    bulk=np.where(wet,bulk,cfg.mold_temperature)

    bulk_rate=cfg.bulk_cooling_rate+cfg.wall_bulk_cooling_rate*wall_factor
    bulk-=bulk_rate*(bulk-cfg.mold_temperature)*dt*wet

    reheat=np.clip(flow_activity/.018,0.,1.)
    reheat=np.maximum(reheat,np.clip(source_depth/.020,0.,1.))
    skin+=cfg.skin_reheat_rate*reheat*(bulk-skin)*dt

    skin_rate=cfg.skin_exchange_rate+cfg.wall_skin_exchange_rate*wall_factor
    skin-=skin_rate*(skin-cfg.mold_temperature)*dt*wet

    sigma=5.670374419e-8
    cap=cfg.density*cfg.heat_capacity*cfg.skin_thickness
    radiative=cfg.surface_emissivity*sigma*np.maximum(
        skin**4-cfg.mold_temperature**4,0.)/max(cap,1e-12)
    skin-=radiative*dt*wet

    skin=np.where(wet,np.minimum(skin,bulk+28.),cfg.mold_temperature)
    bulk=np.clip(bulk,cfg.mold_temperature,cfg.feed_temperature+40.)
    skin=np.clip(skin,cfg.mold_temperature,cfg.feed_temperature+20.)
    return bulk,skin


def _thermal_shock_damage(damage,old_skin,new_skin,flow_activity,wall_factor,dt,cfg):
    crust=1.-_phase_fraction(new_skin,cfg)
    strain=np.clip(flow_activity/.010,0.,4.)
    cooling=np.maximum(old_skin-new_skin,0.)/max(dt,1e-12)
    cooling=np.clip(cooling/320.,0.,3.)
    grow=(.18*crust*np.clip(strain-.10,0.,1.)
          +.075*crust*(1.-np.exp(-strain))
          +.055*crust*cooling*(.35+.65*wall_factor))
    return np.clip(damage+dt*grow,0.,.98)


def _step(h,bulk,skin,damage,mask,labels,wall_factor,sources,t,dt,cfg):
    src_h,src_e,impact,active=_active_source_fields(t,sources,h.shape,cfg)
    qx,qy,kmax=_face_fluxes(h,bulk,skin,mask,cfg.dx,cfg.dy,cfg,impact=impact)

    dh=_divergence(qx,qy,cfg.dx,cfg.dy,h.shape)+src_h
    energy=h*bulk
    ex,ey=_advected_scalar_flux(qx,qy,bulk)
    denergy=_divergence(ex,ey,cfg.dx,cfg.dy,h.shape)+src_e

    h_raw=np.where(mask,np.maximum(h+dt*dh,0.),0.)
    energy_new=energy+dt*denergy
    h_new,energy_new=_redistribute_overflow(
        h_raw,labels,cfg.max_depth,energy=energy_new,sweeps=4)

    bulk_new=np.where(
        h_new>cfg.wet_epsilon,
        energy_new/np.maximum(h_new,1e-8),
        cfg.mold_temperature)
    bulk_new=np.clip(bulk_new,cfg.mold_temperature,cfg.feed_temperature+40.)

    flow=np.zeros_like(h_new)
    flow[:,:-1]+=np.abs(qx)
    flow[:,1:]+=np.abs(qx)
    flow[:-1,:]+=np.abs(qy)
    flow[1:,:]+=np.abs(qy)
    flow/=np.maximum(h_new,1e-5)

    added_depth=dt*src_h
    fresh=(h<=cfg.wet_epsilon)&(h_new>cfg.wet_epsilon)
    skin_seed=np.where(fresh,bulk_new,skin)
    source_fraction=np.clip(added_depth/np.maximum(h_new,1e-8),0.,1.)
    skin_seed=(1.-source_fraction)*skin_seed+source_fraction*cfg.feed_skin_temperature

    old_skin=skin_seed.copy()
    bulk_new,skin_new=_thermal_update(
        h_new,bulk_new,skin_seed,src_h,dt,mask,wall_factor,cfg,flow)
    damage_new=_thermal_shock_damage(
        damage,old_skin,skin_new,flow,wall_factor,dt,cfg)

    return h_new,bulk_new,skin_new,damage_new,active,kmax


def _adaptive_dt(h,bulk,skin,mask,remaining,cfg):
    _,_,kmax=_face_fluxes(h,bulk,skin,mask,cfg.dx,cfg.dy,cfg)
    if kmax<=1e-12:
        return min(remaining,cfg.max_dt)
    stable=cfg.cfl*min(cfg.dx,cfg.dy)**2/kmax
    return min(remaining,cfg.max_dt,max(1e-4,stable))


def _append_jet(vertices,faces,temp,damage,rest,center,bottom,top,radius,cfg,phase,direction=(0.,0.)):
    """Short tapered inlet neck with a broad impact foot, not a tall cylinder."""
    base=len(vertices)
    for ring in range(cfg.jet_rings):
        u=ring/(cfg.jet_rings-1)
        z=bottom+(top-bottom)*u
        # Wide impact skirt at u=0, quickly tapering to a narrow feed.
        flare=1.+(cfg.impact_flare-1.)*math.exp(-u*7.0)
        taper=.58+.42*(1.-u)
        rr=radius*flare*taper*(1.+.035*math.sin(phase+u*9.))
        tx,ty=direction
        # Bottom ring is the impact point. The nozzle end leans upstream so the
        # falling filament has a visible trajectory into the stroke.
        cx=center[0]-tx*cfg.jet_lean*u+radius*.040*math.sin(phase+u*4.7)
        cy=center[1]-ty*cfg.jet_lean*u+radius*.035*math.cos(phase*.8+u*5.2)
        for j in range(cfg.jet_segments):
            a=2.*math.pi*j/cfg.jet_segments
            vertices.append([cx+rr*math.cos(a),cy+rr*math.sin(a),z])
            temp.append(cfg.feed_temperature)
            damage.append(0.)
            rest.append([center[0]+rr*math.cos(a),center[1]+rr*math.sin(a),z])
    for ring in range(cfg.jet_rings-1):
        for j in range(cfg.jet_segments):
            a=base+ring*cfg.jet_segments+j
            b=base+ring*cfg.jet_segments+(j+1)%cfg.jet_segments
            c=base+(ring+1)*cfg.jet_segments+(j+1)%cfg.jet_segments
            d=base+(ring+1)*cfg.jet_segments+j
            faces.extend([(a,b,c),(a,c,d)])


def build_surface_mesh(h,skin,bulk,damage,mask,xs,ys,active_sources,sources,t,cfg,formation,tangent_x=None,tangent_y=None):
    wet=(h>cfg.wet_epsilon)&mask
    if not np.any(wet):
        iy,ix=sources[0]["iy"],sources[0]["ix"]
        wet[iy,ix]=True
        h=h.copy();h[iy,ix]=cfg.wet_epsilon*1.2

    ny,nx=h.shape
    node_h=np.zeros((ny+1,nx+1),np.float64)
    node_t=np.zeros_like(node_h)
    node_bulk=np.zeros_like(node_h)
    node_d=np.zeros_like(node_h)
    node_tx=np.zeros_like(node_h)
    node_ty=np.zeros_like(node_h)
    count=np.zeros_like(node_h)
    if tangent_x is None:
        tangent_x=np.ones_like(h)
    if tangent_y is None:
        tangent_y=np.zeros_like(h)

    for oy,ox in ((0,0),(0,1),(1,0),(1,1)):
        node_h[oy:oy+ny,ox:ox+nx]+=h*wet
        node_t[oy:oy+ny,ox:ox+nx]+=skin*wet
        node_bulk[oy:oy+ny,ox:ox+nx]+=bulk*wet
        node_d[oy:oy+ny,ox:ox+nx]+=damage*wet
        node_tx[oy:oy+ny,ox:ox+nx]+=tangent_x*wet
        node_ty[oy:oy+ny,ox:ox+nx]+=tangent_y*wet
        count[oy:oy+ny,ox:ox+nx]+=wet

    valid=count>0
    node_h[valid]/=count[valid]
    node_t[valid]/=count[valid]
    node_bulk[valid]/=count[valid]
    node_d[valid]/=count[valid]
    node_tx[valid]/=count[valid]
    node_ty[valid]/=count[valid]
    tangent_norm=np.maximum(np.hypot(node_tx,node_ty),1e-9)
    node_tx/=tangent_norm
    node_ty/=tangent_norm

    xnodes=np.linspace(xs[0]-cfg.dx*.5,xs[-1]+cfg.dx*.5,nx+1)
    ynodes=np.linspace(ys[0]-cfg.dy*.5,ys[-1]+cfg.dy*.5,ny+1)
    index=-np.ones((ny+1,nx+1),np.int64)
    vertices=[];temps=[];bulktemps=[];damages=[];rests=[];faces=[]

    for iy in range(ny+1):
        for ix in range(nx+1):
            if not valid[iy,ix]:
                continue
            index[iy,ix]=len(vertices)
            x=float(xnodes[ix]);y=float(ynodes[iy])
            T=float(node_t[iy,ix])
            crust=float(1.-_phase_fraction(np.array([T]),cfg)[0])
            depth_gate=min(1.,max(0.,node_h[iy,ix]/max(cfg.target_depth*.55,1e-8)))
            tx=float(node_tx[iy,ix]);ty=float(node_ty[iy,ix])
            along=x*tx+y*ty
            cross=-x*ty+y*tx
            phase=2.*math.pi*along/cfg.rope_wavelength + .52*math.sin(
                2.*math.pi*cross/(cfg.rope_wavelength*3.7))
            ridge=(.5+.5*math.sin(phase))**3-.3125
            billow=math.sin(
                2.*math.pi*along/cfg.billow_wavelength+
                .45*math.sin(2.*math.pi*cross/(cfg.billow_wavelength*1.6)))
            surface_offset=depth_gate*crust*(
                cfg.rope_amplitude*ridge+cfg.billow_amplitude*.5*billow)
            z=cfg.floor+max(.00005,node_h[iy,ix]+surface_offset)
            vertices.append([x,y,z])
            temps.append(T)
            bulktemps.append(float(node_bulk[iy,ix]))
            damages.append(float(node_d[iy,ix]))
            # Fixed horizontal material coordinates keep optical breakup stable
            # while the resolved height evolves.
            rests.append([xnodes[ix],ynodes[iy],cfg.floor])

    for iy in range(ny):
        for ix in range(nx):
            if not wet[iy,ix]:
                continue
            a=index[iy,ix];b=index[iy,ix+1]
            c=index[iy+1,ix+1];d=index[iy+1,ix]
            if min(a,b,c,d)>=0:
                faces.extend([(a,b,c),(a,c,d)])

    def add_side(top_a,top_b):
        pa=np.asarray(vertices[top_a]);pb=np.asarray(vertices[top_b])
        ia=len(vertices);ib=ia+1
        vertices.extend([
            [pa[0],pa[1],cfg.floor+.00005],
            [pb[0],pb[1],cfg.floor+.00005]])
        ta=.5*(temps[top_a]+temps[top_b])
        tb=.5*(bulktemps[top_a]+bulktemps[top_b])
        da=.5*(damages[top_a]+damages[top_b])
        temps.extend([ta,ta]);bulktemps.extend([tb,tb]);damages.extend([da,da])
        rests.extend([
            [pa[0],pa[1],cfg.floor],
            [pb[0],pb[1],cfg.floor]])
        faces.extend([(top_a,top_b,ib),(top_a,ib,ia)])

    for iy in range(ny):
        for ix in range(nx):
            if not wet[iy,ix]:
                continue
            if iy==0 or not wet[iy-1,ix]:
                add_side(index[iy,ix+1],index[iy,ix])
            if iy==ny-1 or not wet[iy+1,ix]:
                add_side(index[iy+1,ix],index[iy+1,ix+1])
            if ix==0 or not wet[iy,ix-1]:
                add_side(index[iy,ix],index[iy+1,ix])
            if ix==nx-1 or not wet[iy,ix+1]:
                add_side(index[iy+1,ix+1],index[iy,ix+1])

    for src_index in active_sources:
        src=sources[src_index]
        bottom=cfg.floor+float(h[src["iy"],src["ix"]])
        physical_top=formation.nozzle_bottom
        top=min(physical_top,bottom+cfg.jet_visible_height)
        if top>bottom+.003:
            before=len(vertices)
            _append_jet(
                vertices,faces,temps,damages,rests,
                (src["x"],src["y"]),bottom,top,cfg.jet_radius,cfg,
                phase=1.7*src_index+t*3.1,
                direction=(float(src.get("tx",0.)),float(src.get("ty",0.))))
            bulktemps.extend([cfg.feed_temperature]*(len(vertices)-before))

    return {
        "vertices":np.asarray(vertices,np.float32),
        "faces":np.asarray(faces,np.int32),
        "temperature":np.asarray(temps,np.float32),
        "bulkTemperature":np.asarray(bulktemps,np.float32),
        "damage":np.asarray(damages,np.float32),
        "rest":np.asarray(rests,np.float32),
    }


def initialize(source_path:Path,formation:PourFormationConfig,cfg:ShallowLavaConfig):
    with np.load(source_path,allow_pickle=False) as data:
        sdf=np.asarray(data["sdf"],np.float64)
        arrival=np.asarray(data["arrival"],np.float64)
        dirx=np.asarray(data["dirx"],np.float64)
        diry=np.asarray(data["dirz"],np.float64)
        lo=np.asarray(data["lo"],np.float64)
        extent=np.asarray(data["extent"],np.float64)

    xs=np.linspace(cfg.x_min,cfg.x_max,cfg.nx)
    ys=np.linspace(cfg.y_min,cfg.y_max,cfg.ny)
    xx,yy=np.meshgrid(xs,ys,indexing="xy")

    distance=_sample_source_field(
        sdf,xx,yy,lo,extent,formation)*formation.stage_scale
    arrival_stage=_sample_source_field(
        arrival,xx,yy,lo,extent,formation)
    tangent_x=_sample_source_field(
        dirx,xx,yy,lo,extent,formation)
    tangent_y=_sample_source_field(
        diry,xx,yy,lo,extent,formation)
    tangent_norm=np.maximum(np.hypot(tangent_x,tangent_y),1e-8)
    tangent_x/=tangent_norm;tangent_y/=tangent_norm

    mask=distance>max(.0012,min(cfg.dx,cfg.dy)*.22)
    labels,components,inlets=_component_inlets(
        mask,distance,arrival_stage,xx,yy,formation,tangent_x,tangent_y)

    area=float(mask.sum()*cfg.dx*cfg.dy)
    target_volume=area*cfg.target_depth
    sources=_inlet_sources(
        mask,labels,inlets,xx,yy,cfg.dx,cfg.dy,cfg.target_depth,cfg)

    source_volume=sum(src["assignedVolumeM3"] for src in sources)
    if abs(source_volume-target_volume)/max(target_volume,1e-12)>5e-3:
        raise RuntimeError(
            f"inlet capacity partition mismatch: {source_volume} vs {target_volume}")

    wall_factor=np.exp(-np.maximum(distance,0.)/cfg.wall_cooling_length)
    wall_factor=np.clip(wall_factor,0.,1.)*mask

    h=np.zeros(mask.shape,np.float64)
    bulk=np.full(mask.shape,cfg.mold_temperature,np.float64)
    skin=np.full(mask.shape,cfg.mold_temperature,np.float64)
    damage=np.zeros(mask.shape,np.float64)

    return {
        "xs":xs,"ys":ys,"xx":xx,"yy":yy,
        "distance":distance,"wallFactor":wall_factor,
        "tangentX":tangent_x,"tangentY":tangent_y,
        "mask":mask,"labels":labels,
        "components":components,"sources":sources,
        "h":h,"bulk":bulk,"skin":skin,"damage":damage,
        "targetVolumeM3":target_volume,
        "cavityAreaM2":area,
        "lo":lo,"extent":extent,
    }


def advance_state(state,t0,t1,cfg):
    t=float(t0)
    while t<t1-1e-12:
        dt=_adaptive_dt(
            state["h"],state["bulk"],state["skin"],state["mask"],t1-t,cfg)
        state["h"],state["bulk"],state["skin"],state["damage"],active,kmax=_step(
            state["h"],state["bulk"],state["skin"],state["damage"],
            state["mask"],state["labels"],state["wallFactor"],
            state["sources"],t,dt,cfg)
        t+=dt
    _,_,_,active=_active_source_fields(
        t1,state["sources"],state["h"].shape,cfg)
    return active


def metrics(state,t,cfg):
    h=state["h"]
    wet=h>cfg.wet_epsilon
    volume=float(h.sum()*cfg.dx*cfg.dy)
    target=float(state["targetVolumeM3"])

    skin=state["skin"][wet] if np.any(wet) else np.array([cfg.mold_temperature])
    bulk=state["bulk"][wet] if np.any(wet) else np.array([cfg.mold_temperature])
    crust=1.-_phase_fraction(skin,cfg)
    obsidian=_smoothstep(np.clip((cfg.solidus-skin)/220.,0.,1.))

    injected=sum(
        src["flowRateM3s"]*_source_envelope_integral(src,t)
        for src in state["sources"])

    cavity_cells=int(np.count_nonzero(state["mask"]))
    wet_cells=int(wet.sum())

    return {
        "time":float(t),
        "volumeM3":volume,
        "targetVolumeM3":target,
        "volumeRelativeToTarget":volume/max(target,1e-12),
        "maximumDepthM":float(h.max()),
        "meanWetDepthM":float(h[wet].mean()) if np.any(wet) else 0.,
        "scheduledInjectedVolumeM3":float(injected),
        "massBalanceRelative":float((volume-injected)/max(target,1e-12)),
        "cavityCells":cavity_cells,
        "wetCells":wet_cells,
        "wetCoverageFraction":float(wet_cells/max(cavity_cells,1)),
        "skinTemperatureMinK":float(skin.min()),
        "skinTemperatureMeanK":float(skin.mean()),
        "skinTemperatureMaxK":float(skin.max()),
        "bulkTemperatureMeanK":float(bulk.mean()),
        "crustFractionMean":float(crust.mean()),
        "obsidianFractionMean":float(obsidian.mean()),
        "damageMean":float(state["damage"][wet].mean()) if np.any(wet) else 0.,
    }
