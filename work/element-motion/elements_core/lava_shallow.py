"""Depth-averaged viscous lava formation for the CYBRDELIC glyph mold.

This solver is intentionally specialized for the shallow engraved mold used by
the lava formation film. It solves a conservative lubrication-style free-surface
height field on the horizontal cavity plane, transports bulk heat with the
volume flux, evolves a rapidly cooling surface skin, and emits explicit vertical
inlet jets while the source is active.

It does not morph a target mesh, keyframe material into the letters, or use a
render mask. The signed-distance artwork defines rigid no-flux cavity walls; all
material enters through localized inlet source terms and subsequently spreads by
pressure-driven depth-averaged flow.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import math
import numpy as np
from scipy.ndimage import gaussian_filter, label

from .lava_formation import PourFormationConfig, _bilinear, _source_coords


@dataclass(frozen=True)
class ShallowLavaConfig:
    nx: int = 224
    ny: int = 112
    x_min: float = -.70
    x_max: float = .70
    y_min: float = -.34
    y_max: float = .34
    floor: float = .032
    wall_height: float = .052
    target_depth: float = .043
    pour_duration: float = 2.8
    inlet_stagger_seconds: float = 1.15
    feed_temperature: float = 1575.
    feed_skin_temperature: float = 1390.
    mold_temperature: float = 430.
    density: float = 2600.
    gravity: float = 9.81
    viscosity_hot: float = 180.
    viscosity_cold: float = 2.5e5
    solidus: float = 1250.
    liquidus: float = 1450.
    heat_capacity: float = 1200.
    skin_thickness: float = .0018
    skin_exchange_rate: float = .72
    skin_reheat_rate: float = 2.2
    bulk_cooling_rate: float = .055
    surface_emissivity: float = .90
    surface_tension_smoothing: float = .00055
    max_mobility: float = .0045
    cfl: float = .18
    wet_epsilon: float = .00045
    max_depth: float = .050
    jet_radius: float = .0065
    jet_rings: int = 7
    jet_segments: int = 12

    def __post_init__(self):
        if min(self.nx, self.ny) < 32:
            raise ValueError("shallow grid too small")
        if not self.x_max > self.x_min or not self.y_max > self.y_min:
            raise ValueError("invalid shallow domain")
        if not 0 < self.target_depth < self.wall_height:
            raise ValueError("target depth must lie below mold wall")
        if self.pour_duration <= 0 or self.viscosity_hot <= 0:
            raise ValueError("invalid source or viscosity")
        if self.liquidus <= self.solidus:
            raise ValueError("invalid phase interval")
        if self.jet_rings < 2 or self.jet_segments < 6:
            raise ValueError("jet tessellation too small")

    @property
    def dx(self):
        return (self.x_max-self.x_min)/(self.nx-1)

    @property
    def dy(self):
        return (self.y_max-self.y_min)/(self.ny-1)

    def manifest(self):
        return asdict(self)


def _smoothstep(x):
    x=np.clip(x,0.,1.)
    return x*x*(3.-2.*x)


def _sample_source_field(field, xx, yy, lo, extent, formation):
    xy=np.stack([xx,yy],axis=-1)
    v,u=_source_coords(xy,lo,extent,field.shape,formation)
    return _bilinear(field,v,u)


def _component_inlets(mask, distance, arrival, xx, yy, formation):
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
        for q in np.linspace(.08,.92,count_here):
            target_x=np.quantile(px0,q) if count_here>1 else np.median(px0)
            score=np.abs(px0-target_x)+.18*np.abs(py0-np.median(py0))
            idx=int(np.argmin(score))
            iy,ix=int(py0[idx]),int(px0[idx])
            rows.append({
                "component":int(component),
                "areaCells":int(area),
                "ix":ix,"iy":iy,
                "x":float(xx[iy,ix]),"y":float(yy[iy,ix]),
                "arrival":float(arrival[iy,ix]),
                "clearance":float(distance[iy,ix]),
            })
    return labels,components,rows


def _inlet_sources(mask, labels, inlets, xx, yy, dx, dy, target_volume, cfg):
    groups={}
    for i,row in enumerate(inlets):
        groups.setdefault(row["component"],[]).append(i)
    component_cells={k:int(np.count_nonzero(labels==k)) for k in groups}
    total_cells=max(1,sum(component_cells.values()))
    arrival=np.array([r["arrival"] for r in inlets],np.float64)
    amin=float(arrival.min());amax=float(arrival.max())
    span=max(amax-amin,1e-9)
    sources=[]
    for i,row in enumerate(inlets):
        comp=row["component"]
        component_fraction=component_cells[comp]/total_cells
        assigned_volume=target_volume*component_fraction/len(groups[comp])
        start=cfg.inlet_stagger_seconds*(row["arrival"]-amin)/span
        end=start+cfg.pour_duration
        sigma=min(.012,max(.0045,row["clearance"]*.34))
        r2=(xx-row["x"])**2+(yy-row["y"])**2
        weight=np.exp(-.5*r2/(sigma*sigma))*mask*(labels==comp)
        norm=float(weight.sum()*dx*dy)
        if norm<=0:
            raise RuntimeError("empty inlet support")
        shape=weight/norm
        sources.append({
            **row,
            "start":float(start),"end":float(end),
            "assignedVolumeM3":float(assigned_volume),
            "flowRateM3s":float(assigned_volume/cfg.pour_duration),
            "sigma":float(sigma),
            "shape":shape.astype(np.float64),
        })
    return sources


def _viscosity(skin_temperature,cfg):
    phase=np.clip((cfg.liquidus-skin_temperature)/(cfg.liquidus-cfg.solidus),0.,1.)
    phase=_smoothstep(phase)
    log_mu=np.log(cfg.viscosity_hot)+(np.log(cfg.viscosity_cold)-np.log(cfg.viscosity_hot))*phase
    return np.exp(log_mu)


def _face_fluxes(h,skin,mask,dx,dy,cfg):
    mu=_viscosity(skin,cfg)
    hx=.5*(h[:,:-1]+h[:,1:])
    mux=np.sqrt(mu[:,:-1]*mu[:,1:])
    kx=cfg.density*cfg.gravity*hx**3/(3.*np.maximum(mux,1e-9))
    kx=np.minimum(kx,cfg.max_mobility)
    qx=-kx*(h[:,1:]-h[:,:-1])/dx
    qx*=mask[:,:-1]&mask[:,1:]

    hy=.5*(h[:-1,:]+h[1:,:])
    muy=np.sqrt(mu[:-1,:]*mu[1:,:])
    ky=cfg.density*cfg.gravity*hy**3/(3.*np.maximum(muy,1e-9))
    ky=np.minimum(ky,cfg.max_mobility)
    qy=-ky*(h[1:,:]-h[:-1,:])/dy
    qy*=mask[:-1,:]&mask[1:,:]
    return qx,qy,float(max(kx.max(initial=0.),ky.max(initial=0.)))


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


def _active_source_fields(t,sources,shape,cfg):
    depth_rate=np.zeros(shape,np.float64)
    heat_rate=np.zeros(shape,np.float64)
    active=[]
    for i,src in enumerate(sources):
        if src["start"]<=t<src["end"]:
            local=src["flowRateM3s"]*src["shape"]
            depth_rate+=local
            heat_rate+=local*cfg.feed_temperature
            active.append(i)
    return depth_rate,heat_rate,active


def _thermal_update(h,bulk,skin,source_depth,source_heat,dt,mask,cfg,flow_activity):
    wet=h>cfg.wet_epsilon
    bulk=np.where(wet,bulk,cfg.mold_temperature)
    bulk-=cfg.bulk_cooling_rate*(bulk-cfg.mold_temperature)*dt*wet

    reheat=np.clip(flow_activity/.018,0.,1.)
    reheat=np.maximum(reheat,np.clip(source_depth/.025,0.,1.))
    skin+=cfg.skin_reheat_rate*reheat*(bulk-skin)*dt
    skin-=cfg.skin_exchange_rate*(skin-cfg.mold_temperature)*dt*wet

    sigma=5.670374419e-8
    cap=cfg.density*cfg.heat_capacity*cfg.skin_thickness
    radiative=cfg.surface_emissivity*sigma*np.maximum(skin**4-cfg.mold_temperature**4,0.)/max(cap,1e-12)
    skin-=radiative*dt*wet
    skin=np.where(wet,np.minimum(skin,bulk+35.),cfg.mold_temperature)
    return bulk,skin


def _thermal_shock_damage(damage,skin,flow_activity,dt,cfg):
    crust=_smoothstep(np.clip((cfg.liquidus-skin)/(cfg.liquidus-cfg.solidus),0.,1.))
    strain=np.clip(flow_activity/.012,0.,4.)
    grow=.22*crust*np.clip(strain-.15,0.,1.)+.055*crust*(1.-np.exp(-strain))
    return np.clip(damage+dt*grow,0.,.98)


def _step(h,bulk,skin,damage,mask,sources,t,dt,cfg):
    qx,qy,kmax=_face_fluxes(h,skin,mask,cfg.dx,cfg.dy,cfg)
    src_h,src_e,active=_active_source_fields(t,sources,h.shape,cfg)

    dh=_divergence(qx,qy,cfg.dx,cfg.dy,h.shape)+src_h
    energy=h*bulk
    ex,ey=_advected_scalar_flux(qx,qy,bulk)
    denergy=_divergence(ex,ey,cfg.dx,cfg.dy,h.shape)+src_e

    h_new=h+dt*dh
    h_new=np.where(mask,np.clip(h_new,0.,cfg.max_depth),0.)
    energy_new=energy+dt*denergy
    bulk_new=np.where(h_new>cfg.wet_epsilon,
                      energy_new/np.maximum(h_new,1e-8),
                      cfg.mold_temperature)
    bulk_new=np.clip(bulk_new,cfg.mold_temperature,cfg.feed_temperature+60.)

    if cfg.surface_tension_smoothing>0:
        smooth=gaussian_filter(h_new,.55,mode="nearest")
        h_new=np.where(mask,
            h_new+cfg.surface_tension_smoothing*dt*(smooth-h_new)/(max(cfg.dx,cfg.dy)**2),
            0.)
        h_new=np.clip(h_new,0.,cfg.max_depth)

    flow=np.zeros_like(h_new)
    flow[:,:-1]+=np.abs(qx)
    flow[:,1:]+=np.abs(qx)
    flow[:-1,:]+=np.abs(qy)
    flow[1:,:]+=np.abs(qy)
    flow/=np.maximum(h_new,1e-5)

    bulk_new,skin_new=_thermal_update(
        h_new,bulk_new,skin,src_h,src_e,dt,mask,cfg,flow)
    damage_new=_thermal_shock_damage(damage,skin_new,flow,dt,cfg)
    return h_new,bulk_new,skin_new,damage_new,active,kmax


def _adaptive_dt(h,skin,remaining,cfg):
    _,_,kmax=_face_fluxes(h,skin,np.ones_like(h,dtype=bool),cfg.dx,cfg.dy,cfg)
    if kmax<=1e-12:
        return min(remaining,.008)
    stable=cfg.cfl*min(cfg.dx,cfg.dy)**2/kmax
    return min(remaining,.008,max(2e-4,stable))


def _append_jet(vertices,faces,temp,damage,rest,center,bottom,top,radius,cfg,phase):
    base=len(vertices)
    for ring in range(cfg.jet_rings):
        u=ring/(cfg.jet_rings-1)
        z=bottom+(top-bottom)*u
        rr=radius*(.88+.10*math.sin(phase+u*7.1)+.045*math.sin(phase*.7+u*17.))
        cx=center[0]+radius*.12*math.sin(phase+u*5.3)
        cy=center[1]+radius*.10*math.cos(phase*.8+u*4.7)
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


def build_surface_mesh(h,skin,damage,mask,xs,ys,active_sources,sources,t,cfg,formation):
    wet=(h>cfg.wet_epsilon)&mask
    if not np.any(wet):
        iy,ix=sources[0]["iy"],sources[0]["ix"]
        wet[iy,ix]=True
        h=h.copy();h[iy,ix]=cfg.wet_epsilon*1.2

    ny,nx=h.shape
    node_h=np.zeros((ny+1,nx+1),np.float64)
    node_t=np.zeros_like(node_h)
    node_d=np.zeros_like(node_h)
    count=np.zeros_like(node_h)
    for oy,ox in ((0,0),(0,1),(1,0),(1,1)):
        node_h[oy:oy+ny,ox:ox+nx]+=h*wet
        node_t[oy:oy+ny,ox:ox+nx]+=skin*wet
        node_d[oy:oy+ny,ox:ox+nx]+=damage*wet
        count[oy:oy+ny,ox:ox+nx]+=wet
    valid=count>0
    node_h[valid]/=count[valid]
    node_t[valid]/=count[valid]
    node_d[valid]/=count[valid]

    xnodes=np.linspace(xs[0]-cfg.dx*.5,xs[-1]+cfg.dx*.5,nx+1)
    ynodes=np.linspace(ys[0]-cfg.dy*.5,ys[-1]+cfg.dy*.5,ny+1)
    index=-np.ones((ny+1,nx+1),np.int64)
    vertices=[];temps=[];damages=[];rests=[];faces=[]
    for iy in range(ny+1):
        for ix in range(nx+1):
            if not valid[iy,ix]:
                continue
            index[iy,ix]=len(vertices)
            z=cfg.floor+max(0.,node_h[iy,ix])
            vertices.append([xnodes[ix],ynodes[iy],z])
            temps.append(float(node_t[iy,ix]))
            damages.append(float(node_d[iy,ix]))
            rests.append([xnodes[ix],ynodes[iy],z])
    for iy in range(ny):
        for ix in range(nx):
            if not wet[iy,ix]:
                continue
            a=index[iy,ix];b=index[iy,ix+1];c=index[iy+1,ix+1];d=index[iy+1,ix]
            if min(a,b,c,d)>=0:
                faces.extend([(a,b,c),(a,c,d)])

    def add_side(top_a,top_b):
        pa=np.asarray(vertices[top_a]);pb=np.asarray(vertices[top_b])
        ia=len(vertices);ib=ia+1
        vertices.extend([[pa[0],pa[1],cfg.floor+.00005],[pb[0],pb[1],cfg.floor+.00005]])
        ta=.5*(temps[top_a]+temps[top_b]);da=.5*(damages[top_a]+damages[top_b])
        temps.extend([ta,ta]);damages.extend([da,da])
        rests.extend([[pa[0],pa[1],cfg.floor],[pb[0],pb[1],cfg.floor]])
        faces.extend([(top_a,top_b,ib),(top_a,ib,ia)])

    for iy in range(ny):
        for ix in range(nx):
            if not wet[iy,ix]: continue
            if iy==0 or not wet[iy-1,ix]: add_side(index[iy,ix+1],index[iy,ix])
            if iy==ny-1 or not wet[iy+1,ix]: add_side(index[iy+1,ix],index[iy+1,ix+1])
            if ix==0 or not wet[iy,ix-1]: add_side(index[iy,ix],index[iy+1,ix])
            if ix==nx-1 or not wet[iy,ix+1]: add_side(index[iy+1,ix+1],index[iy,ix+1])

    for src_index in active_sources:
        src=sources[src_index]
        bottom=cfg.floor+float(h[src["iy"],src["ix"]])
        top=formation.nozzle_bottom
        if top>bottom+.004:
            _append_jet(vertices,faces,temps,damages,rests,
                        (src["x"],src["y"]),bottom,top,cfg.jet_radius,cfg,
                        phase=1.7*src_index+t*3.1)

    return {
        "vertices":np.asarray(vertices,np.float32),
        "faces":np.asarray(faces,np.int32),
        "temperature":np.asarray(temps,np.float32),
        "damage":np.asarray(damages,np.float32),
        "rest":np.asarray(rests,np.float32),
    }


def initialize(source_path:Path,formation:PourFormationConfig,cfg:ShallowLavaConfig):
    with np.load(source_path,allow_pickle=False) as data:
        sdf=np.asarray(data["sdf"],np.float64)
        arrival=np.asarray(data["arrival"],np.float64)
        lo=np.asarray(data["lo"],np.float64)
        extent=np.asarray(data["extent"],np.float64)

    xs=np.linspace(cfg.x_min,cfg.x_max,cfg.nx)
    ys=np.linspace(cfg.y_min,cfg.y_max,cfg.ny)
    xx,yy=np.meshgrid(xs,ys,indexing="xy")
    distance=_sample_source_field(sdf,xx,yy,lo,extent,formation)*formation.stage_scale
    arrival_stage=_sample_source_field(arrival,xx,yy,lo,extent,formation)
    mask=distance>max(.0015,min(cfg.dx,cfg.dy)*.30)
    labels,components,inlets=_component_inlets(mask,distance,arrival_stage,xx,yy,formation)
    area=float(mask.sum()*cfg.dx*cfg.dy)
    target_volume=area*cfg.target_depth
    sources=_inlet_sources(mask,labels,inlets,xx,yy,cfg.dx,cfg.dy,target_volume,cfg)

    h=np.zeros(mask.shape,np.float64)
    bulk=np.full(mask.shape,cfg.mold_temperature,np.float64)
    skin=np.full(mask.shape,cfg.mold_temperature,np.float64)
    damage=np.zeros(mask.shape,np.float64)
    return {
        "xs":xs,"ys":ys,"xx":xx,"yy":yy,"distance":distance,
        "mask":mask,"labels":labels,"components":components,"sources":sources,
        "h":h,"bulk":bulk,"skin":skin,"damage":damage,
        "targetVolumeM3":target_volume,"cavityAreaM2":area,
        "lo":lo,"extent":extent,
    }


def advance_state(state,t0,t1,cfg):
    t=float(t0)
    while t<t1-1e-12:
        dt=_adaptive_dt(state["h"],state["skin"],t1-t,cfg)
        state["h"],state["bulk"],state["skin"],state["damage"],active,kmax=_step(
            state["h"],state["bulk"],state["skin"],state["damage"],
            state["mask"],state["sources"],t,dt,cfg)
        t+=dt
    _,_,active=_active_source_fields(t1,state["sources"],state["h"].shape,cfg)
    return active


def metrics(state,t,cfg):
    h=state["h"];wet=h>cfg.wet_epsilon
    volume=float(h.sum()*cfg.dx*cfg.dy)
    target=float(state["targetVolumeM3"])
    skin=state["skin"][wet] if np.any(wet) else np.array([cfg.mold_temperature])
    bulk=state["bulk"][wet] if np.any(wet) else np.array([cfg.mold_temperature])
    crust=_smoothstep(np.clip((cfg.liquidus-skin)/(cfg.liquidus-cfg.solidus),0.,1.))
    obsidian=_smoothstep(np.clip((cfg.solidus-skin)/260.,0.,1.))
    injected=sum(
        src["flowRateM3s"]*max(0.,min(t,src["end"])-src["start"])
        for src in state["sources"]
    )
    return {
        "time":float(t),
        "volumeM3":volume,
        "targetVolumeM3":target,
        "volumeRelativeToTarget":volume/max(target,1e-12),
        "scheduledInjectedVolumeM3":float(injected),
        "massBalanceRelative":float((volume-injected)/max(target,1e-12)),
        "wetCells":int(wet.sum()),
        "skinTemperatureMinK":float(skin.min()),
        "skinTemperatureMeanK":float(skin.mean()),
        "skinTemperatureMaxK":float(skin.max()),
        "bulkTemperatureMeanK":float(bulk.mean()),
        "crustFractionMean":float(crust.mean()),
        "obsidianFractionMean":float(obsidian.mean()),
        "damageMean":float(state["damage"][wet].mean()) if np.any(wet) else 0.,
    }
