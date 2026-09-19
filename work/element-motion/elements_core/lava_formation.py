"""Pour-to-glyph formation for the thermal lava MPM.

The word is a real shallow cavity derived from the approved signed-distance
artwork.  Material starts in compact elevated feed columns, falls under gravity,
and is constrained by the cavity side walls.  There is no target-position
morph, keyframed particle path, or render mask.

The side-wall contact is a particle-level unilateral constraint evaluated after
the authoritative MPM grid update.  It is a reduced rigid-mold boundary model,
not two-way mold deformation or a resolved boundary-fitted pressure solve.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from pathlib import Path
import math
import numpy as np
from numba import njit
from scipy.ndimage import label
from .lava_mpm import LavaConfig, LavaMPM, enthalpy_from_temperature


@dataclass(frozen=True)
class PourFormationConfig:
    stage_scale: float = .15
    source_center_z: float = 1.95
    fill_height: float = .048
    wall_height: float = .052
    nozzle_bottom: float = .17
    nozzle_radius_main: float = .025
    nozzle_radius_small: float = .020
    main_nozzles: int = 6
    wall_margin_fraction: float = .22
    inlet_speed: float = .34
    inlet_stagger_scale: float = .55
    tangent_speed: float = .055
    initial_down_speed: float = .38
    source_longitudinal_subdivisions: int = 3
    skin_temperature: float = 1320.
    core_temperature: float = 1580.
    mold_contact_conductance: float = 2600.
    mold_temperature: float = 450.
    thermal_contact_band_fraction: float = .85
    significant_component_pixels: int = 100

    def __post_init__(self):
        if self.stage_scale <= 0 or self.fill_height <= 0 or self.wall_height <= 0:
            raise ValueError('invalid formation scale')
        if self.main_nozzles < 1 or self.nozzle_radius_main <= 0 or self.nozzle_radius_small <= 0:
            raise ValueError('invalid nozzle configuration')
        if self.inlet_speed <= 0 or self.initial_down_speed <= 0 or self.tangent_speed < 0 or self.inlet_stagger_scale < 0:
            raise ValueError('invalid inlet velocity/timing configuration')
        if self.source_longitudinal_subdivisions < 1:
            raise ValueError('source longitudinal subdivisions must be positive')
        if self.mold_contact_conductance <= 0 or self.mold_temperature <= 0 or self.thermal_contact_band_fraction <= 0:
            raise ValueError('invalid mold thermal coupling')
        if self.core_temperature <= self.skin_temperature:
            raise ValueError('core must be hotter than nozzle skin')

    def manifest(self):
        return asdict(self)


def _bilinear(field, y, x):
    h,w=field.shape
    x=np.clip(x,0,w-1.000001);y=np.clip(y,0,h-1.000001)
    x0=np.floor(x).astype(np.int64);y0=np.floor(y).astype(np.int64)
    x1=np.minimum(x0+1,w-1);y1=np.minimum(y0+1,h-1)
    fx=x-x0;fy=y-y0
    return ((1-fx)*(1-fy)*field[y0,x0] + fx*(1-fy)*field[y0,x1]
            +(1-fx)*fy*field[y1,x0] + fx*fy*field[y1,x1])


def _source_coords(xy, lo, extent, shape, formation: PourFormationConfig):
    sx=xy[...,0]/formation.stage_scale
    sz=xy[...,1]/formation.stage_scale+formation.source_center_z
    u=(sx-lo[0])/extent[0]*(shape[1]-1)
    v=(sz-lo[2])/extent[2]*(shape[0]-1)
    return v,u


def _stage_point(ix,iy,lo,extent,shape,formation):
    sx=lo[0]+ix/(shape[1]-1)*extent[0]
    sz=lo[2]+iy/(shape[0]-1)*extent[2]
    return np.array([sx*formation.stage_scale,
                     (sz-formation.source_center_z)*formation.stage_scale])


def _select_inlets(sdf,arrival,labels,components,lo,extent,formation):
    inlets=[]
    for rank,(component,area) in enumerate(components):
        yy,xx=np.where(labels==component)
        values=sdf[yy,xx]
        deep=values>np.percentile(values,45)
        py,px=yy[deep],xx[deep]
        if rank==0:
            for q in np.linspace(.10,.90,formation.main_nozzles):
                xq=np.quantile(px,q)
                index=np.argmin(np.abs(px-xq)+.15*np.abs(py-np.median(py)))
                iy,ix=int(py[index]),int(px[index])
                inlets.append((_stage_point(ix,iy,lo,extent,sdf.shape,formation),component,ix,iy))
        else:
            vals=arrival[yy,xx]
            finite=np.isfinite(vals)
            if not np.any(finite):
                index=0
            else:
                eligible=np.flatnonzero(finite)
                index=int(eligible[np.argmin(vals[finite])])
            iy,ix=int(yy[index]),int(xx[index])
            inlets.append((_stage_point(ix,iy,lo,extent,sdf.shape,formation),component,ix,iy))
    return inlets


def build_pour_initial_state(source: Path, lava: LavaConfig, *,
                             samples_per_axis=2,
                             formation: PourFormationConfig | None=None):
    formation=formation or PourFormationConfig()
    if samples_per_axis<1:
        raise ValueError('samples_per_axis must be positive')
    with np.load(source,allow_pickle=False) as data:
        sdf=np.asarray(data['sdf'],np.float64)
        arrival=np.asarray(data['arrival'],np.float64)
        dirx=np.asarray(data['dirx'],np.float64)
        dirz=np.asarray(data['dirz'],np.float64)
        lo=np.asarray(data['lo'],np.float64)
        extent=np.asarray(data['extent'],np.float64)

    binary=sdf>0
    labels,count=label(binary)
    components=[]
    for component in range(1,count+1):
        area=int(np.count_nonzero(labels==component))
        if area>=formation.significant_component_pixels:
            components.append((component,area))
    components.sort(key=lambda row:-row[1])
    if not components:
        raise RuntimeError('approved artwork has no resolved cavity components')

    step=lava.spacing/samples_per_axis
    xs=np.arange(-.68,.680001,step)+step*.5
    ys=np.arange(-.32,.320001,step)+step*.5
    zs=np.arange(lava.floor+.004,lava.floor+formation.fill_height,step)+step*.5
    xx,yy,zz=np.meshgrid(xs,ys,zs,indexing='ij')
    target=np.column_stack([xx.ravel(),yy.ravel(),zz.ravel()])
    cv,cu=_source_coords(target[:,:2],lo,extent,sdf.shape,formation)
    distance=_bilinear(sdf,cv,cu)*formation.stage_scale
    target=target[distance>step*.30]
    if len(target)<1000:
        raise RuntimeError('formation cavity contains too few material samples')

    inlets=_select_inlets(sdf,arrival,labels,components,lo,extent,formation)
    cv,cu=_source_coords(target[:,:2],lo,extent,sdf.shape,formation)
    ix=np.clip(np.rint(cu).astype(np.int64),0,sdf.shape[1]-1)
    iy=np.clip(np.rint(cv).astype(np.int64),0,sdf.shape[0]-1)
    target_component=labels[iy,ix]
    assignment=np.empty(len(target),np.int32)
    for q in range(len(target)):
        candidates=[i for i,row in enumerate(inlets) if row[1]==target_component[q]]
        if not candidates:
            candidates=list(range(len(inlets)))
        assignment[q]=min(candidates,key=lambda i:float(np.sum((target[q,:2]-inlets[i][0])**2)))

    rng=np.random.default_rng(83017)
    positions=[];temperatures=[];velocities=[];nozzle_rows=[]
    for inlet_index,(center,component,ix0,iy0) in enumerate(inlets):
        total=int(np.count_nonzero(assignment==inlet_index))
        if not total:
            continue
        requested_radius=formation.nozzle_radius_main if component==components[0][0] else formation.nozzle_radius_small
        center_clearance=max(0.,float(sdf[iy0,ix0])*formation.stage_scale)
        radius=max(step*.18,min(requested_radius,max(step*.18,center_clearance-step*(formation.wall_margin_fraction+.30))))
        tangent=np.array([dirx[iy0,ix0],dirz[iy0,ix0]],np.float64)
        tangent/=max(float(np.linalg.norm(tangent)),1e-12)
        built=0;layer=0;start=len(positions)
        phase=1.7*inlet_index
        minimum_source_clearance=step*(formation.wall_margin_fraction+.20)
        while built<total:
            growth=min(1.,layer/18.)
            effective_radius=radius*(.62+.38*growth)
            # Candidate source samples are explicitly rejected if their x/y
            # footprint crosses the cavity SDF.  This prevents molten source
            # mass from being emitted onto solid mold top faces.
            rr=min(effective_radius,step*.72)
            disk=np.array([[0.,0.],[rr,0.],[-rr,0.],[0.,rr],[0.,-rr]],np.float64)
            wobble_scale=min(step*.07,max(0.,center_clearance-effective_radius-minimum_source_clearance)*.20)
            wobble=np.array([wobble_scale*math.sin(phase+layer*.61),
                             wobble_scale*math.cos(phase*.7+layer*.47)])
            candidate_xy=disk+center[None,:]+wobble[None,:]
            sv,su=_source_coords(candidate_xy,lo,extent,sdf.shape,formation)
            clearance=_bilinear(sdf,sv,su)*formation.stage_scale
            disk=disk[clearance>=minimum_source_clearance]
            if not len(disk):
                # The inlet center itself was selected from the deep interior;
                # retain a single narrow source sample rather than fabricating
                # a ring that extends through a wall.
                disk=np.array([[0.,0.]],np.float64)
                wobble=np.zeros(2,np.float64)
            take=min(len(disk),total-built)
            for a,b in disk[:take]:
                jitter=(rng.random(3)-.5)*step*.08
                xy=np.array([center[0]+wobble[0]+a+jitter[0],
                             center[1]+wobble[1]+b+jitter[1]])
                sv,su=_source_coords(xy[None,:],lo,extent,sdf.shape,formation)
                dxy=float(_bilinear(sdf,sv,su)[0])*formation.stage_scale
                if dxy<minimum_source_clearance:
                    xy=center.copy()
                z=formation.nozzle_bottom+layer*step
                positions.append([xy[0],xy[1],z+jitter[2]])
                radial=min(1.,math.hypot(a,b)/max(effective_radius,step*.18))
                core=(1.-radial)**.55
                temperatures.append(formation.skin_temperature+
                                    (formation.core_temperature-formation.skin_temperature)*core)
                velocities.append([tangent[0]*formation.tangent_speed+.010*math.sin(layer*.43+phase),
                                   tangent[1]*formation.tangent_speed+.008*math.cos(layer*.37+phase),
                                   -(formation.initial_down_speed+.12*growth)])
            built+=take;layer+=1
        nozzle_rows.append({'component':int(component),'particles':total,'radius':radius,
                            'requestedRadius':requested_radius,'centerClearance':center_clearance,
                            'arrival':float(arrival[iy0,ix0]),'center':center.tolist(),'layers':layer,
                            'zMin':formation.nozzle_bottom,
                            'zMax':formation.nozzle_bottom+(layer-1)*step})

    positions=np.asarray(positions,np.float64)
    velocities=np.asarray(velocities,np.float64)
    temperatures=np.asarray(temperatures,np.float64)
    volumes=np.full(len(positions),step**3,np.float64)
    # The vertical columns above are a deterministic source-time parameterization,
    # not simultaneous particles in the transfer grid.  build_pour_source_schedule
    # respawns each layer at nozzle_bottom, so their virtual z extent may exceed
    # the active MPM domain without violating the transfer guard.

    cell_x=extent[0]/(sdf.shape[1]-1)
    cell_z=extent[2]/(sdf.shape[0]-1)
    gz,gx=np.gradient(sdf,cell_z,cell_x)
    norm=np.hypot(gx,gz)
    gx/=np.maximum(norm,1e-12);gz/=np.maximum(norm,1e-12)
    mold={
        'sdf':np.asarray(sdf,np.float64),
        'gx':np.asarray(gx,np.float64),
        'gz':np.asarray(gz,np.float64),
        'lo':lo,'extent':extent,
        'stageScale':formation.stage_scale,
        'sourceCenterZ':formation.source_center_z,
        'wallTop':lava.floor+formation.wall_height,
        'margin':step*formation.wall_margin_fraction,
        'friction':lava.friction,
        'thermalConductance':formation.mold_contact_conductance,
        'moldTemperature':formation.mold_temperature,
        'thermalBand':lava.spacing*formation.thermal_contact_band_fraction,
    }
    report={
        'mode':'gravity-fed shallow cavity',
        'particles':len(positions),
        'targetFillVolumeM3':float(volumes.sum()),
        'targetSamples':len(target),
        'inlets':nozzle_rows,
        'components':[{'label':int(k),'pixels':int(a)} for k,a in components],
        'particleSpacing':step,
        'formation':formation.manifest(),
        'noTargetPositionForces':True,
        'contactModel':'post-G2P unilateral signed-distance mold projection',
    }
    return positions,enthalpy_from_temperature(temperatures,lava),volumes,velocities,mold,report



def build_pour_source_schedule(source: Path, lava: LavaConfig, *,
                               samples_per_axis=2,
                               formation: PourFormationConfig | None=None):
    """Turn resolved feed layers into a timed open-boundary inlet.

    The initial-state builder lays out one material layer per physical particle
    spacing. Here that vertical coordinate becomes source time: layer spacing
    divided by inlet speed. Each layer is spawned at the nozzle plane with its
    actual inlet velocity, so the cavity is filled by sustained mass flux
    instead of dropping the entire reservoir as one preloaded slug.

    The original feed coordinate is retained only as a Lagrangian material
    coordinate for advected BSDF detail. It never exerts a force or specifies
    a target position.
    """
    formation=formation or PourFormationConfig()
    positions,H,V,velocities,mold,report=build_pour_initial_state(
        source,lava,samples_per_axis=samples_per_axis,formation=formation)
    step=lava.spacing/samples_per_axis
    spawn=positions.copy()
    material_coordinates=positions.copy()
    release=np.empty(len(positions),np.float64)
    inlet_arrival=np.array([float(row.get('arrival',0.)) for row in report['inlets']],np.float64)
    arrival0=float(inlet_arrival.min()) if len(inlet_arrival) else 0.
    cursor=0
    for inlet_index,row in enumerate(report['inlets']):
        count=int(row['particles'])
        sl=slice(cursor,cursor+count)
        raw_layer=(positions[sl,2]-formation.nozzle_bottom)/step
        layer=np.maximum(0,np.rint(raw_layer).astype(np.int64))
        delay=max(0.,float(inlet_arrival[inlet_index]-arrival0))*formation.inlet_stagger_scale
        row['startDelaySeconds']=delay
        release[sl]=delay+layer*step/formation.inlet_speed
        residual=positions[sl,2]-(formation.nozzle_bottom+layer*step)
        spawn[sl,2]=formation.nozzle_bottom+np.clip(residual,-step*.09,step*.09)
        cursor+=count
    if cursor!=len(positions):
        raise RuntimeError('source schedule does not cover all feed particles')
    subdivisions=int(formation.source_longitudinal_subdivisions)
    layer_period=step/formation.inlet_speed
    if subdivisions>1:
        sub=np.arange(subdivisions,dtype=np.float64)
        release=(release[:,None]+sub[None,:]*(layer_period/subdivisions)).reshape(-1)
        spawn=np.repeat(spawn,subdivisions,axis=0)
        H=np.repeat(H,subdivisions,axis=0)
        V=np.repeat(V/subdivisions,subdivisions,axis=0)
        velocities=np.repeat(velocities,subdivisions,axis=0)
        rest=np.repeat(material_coordinates,subdivisions,axis=0)
        rest[:,2]+=(np.tile(sub,len(material_coordinates))-(subdivisions-1)*.5)*(step/subdivisions)
        material_coordinates=rest
    order=np.argsort(release,kind='stable')
    schedule={
        'releaseTime':release[order],
        'positions':spawn[order],
        'enthalpy':H[order],
        'volumes':V[order],
        'velocities':velocities[order],
        'materialCoordinates':material_coordinates[order],
        'cursor':0,
    }
    report['sourceBoundaryModel']='timed open-boundary particle injection at resolved nozzle plane'
    report['sourceDurationSeconds']=float(release.max()) if len(release) else 0.
    report['sourceLayerPeriodSeconds']=float(layer_period)
    report['sourceSubstepPeriodSeconds']=float(layer_period/subdivisions)
    report['sourceLongitudinalSubdivisions']=subdivisions
    report['sourceNumericalParticles']=int(len(release))
    report['simultaneousReservoirRelease']=False
    report['sourceMassFluxIsParticleResolved']=True
    report['sourceVolumePreservedAfterSubdivision']=float(V.sum())
    report['inletStaggerScale']=formation.inlet_stagger_scale
    report['moldThermalCoupling']={'conductanceWm2K':formation.mold_contact_conductance,
                                   'moldTemperatureK':formation.mold_temperature,
                                   'contactBandMeters':mold['thermalBand']}
    return schedule,mold,report


def _inject_due_source(sim: LavaMPM,source,through_time: float):
    cursor=int(source.get('cursor',0));times=source['releaseTime']
    end=int(np.searchsorted(times,through_time+1e-12,side='right'))
    if end<=cursor:return 0
    sl=slice(cursor,end)
    added=sim.inject(source['positions'][sl],source['enthalpy'][sl],source['volumes'][sl],
                     source['velocities'][sl],source['materialCoordinates'][sl])
    source['cursor']=end
    return int(added)


def build_mold_mesh(source: Path,lava: LavaConfig,formation: PourFormationConfig|None=None):
    """Build a closed shallow stone mold with genuinely lowered glyph cavities."""
    formation=formation or PourFormationConfig()
    from scipy.ndimage import gaussian_filter
    from skimage.measure import marching_cubes
    with np.load(source,allow_pickle=False) as data:
        sdf=np.asarray(data['sdf'],np.float64);lo=np.asarray(data['lo'],np.float64);extent=np.asarray(data['extent'],np.float64)
    dx=.008;dy=.008;dz=.005
    xs=np.arange(-.74,.740001,dx);ys=np.arange(-.36,.360001,dy)
    z0=lava.floor-.035;z1=lava.floor+formation.wall_height+.018
    zs=np.arange(z0,z1+dz*.5,dz)
    xx,yy=np.meshgrid(xs,ys,indexing='xy')
    cv,cu=_source_coords(np.stack([xx,yy],axis=-1),lo,extent,sdf.shape,formation)
    d=_bilinear(sdf,cv,cu)*formation.stage_scale
    cavity=d>.004
    solid=np.zeros((len(zs),len(ys),len(xs)),np.float32)
    for k,z in enumerate(zs):
        if z<=lava.floor:
            solid[k]=1.
        elif z<=lava.floor+formation.wall_height:
            solid[k]=(~cavity).astype(np.float32)
    solid=gaussian_filter(solid,.55,mode='nearest')
    verts,faces,_,_=marching_cubes(solid,.5,spacing=(dz,dy,dx),allow_degenerate=False)
    verts=verts[:,[2,1,0]]+np.array([xs[0],ys[0],zs[0]])
    report={'vertices':len(verts),'triangles':len(faces),'voxelSpacing':[dx,dy,dz],
            'wallHeight':formation.wall_height,'cavityClearance':.004,
            'method':'binary extruded mold softened only at the sub-voxel boundary'}
    return {'vertices':verts.astype(np.float32),'faces':faces.astype(np.int32)},report


@njit(cache=True,inline='always')
def _sample_bilinear(field,y,x):
    h,w=field.shape
    if x<0:x=0.
    if y<0:y=0.
    if x>w-1.000001:x=w-1.000001
    if y>h-1.000001:y=h-1.000001
    x0=int(math.floor(x));y0=int(math.floor(y))
    x1=min(x0+1,w-1);y1=min(y0+1,h-1)
    fx=x-x0;fy=y-y0
    return ((1-fx)*(1-fy)*field[y0,x0]+fx*(1-fy)*field[y0,x1]
            +(1-fx)*fy*field[y1,x0]+fx*fy*field[y1,x1])


@njit(cache=True)
def _mold_contact(x,v,sdf,gx,gz,lo,extent,scale,center_z,wall_top,margin,friction):
    count=0;maximum=0.
    h,w=sdf.shape
    for q in range(len(x)):
        if x[q,2]>wall_top+margin:
            continue
        sx=x[q,0]/scale
        sz=x[q,1]/scale+center_z
        u=(sx-lo[0])/extent[0]*(w-1)
        vv=(sz-lo[2])/extent[2]*(h-1)
        distance=_sample_bilinear(sdf,vv,u)*scale
        if distance>=margin:
            continue

        # Outside the cavity, the mold has a horizontal top face.  Do not
        # teleport a particle sideways through solid stone: resolve the top
        # impact first.  A stream aimed inside the cavity never takes this
        # branch because its signed distance is positive.
        if distance<0.:
            top=wall_top+margin
            if x[q,2]<top:
                correction=top-x[q,2]
                x[q,2]=top
                normal_speed=max(0.,-v[q,2])
                if v[q,2]<0.:v[q,2]=0.
                tangent=math.sqrt(v[q,0]*v[q,0]+v[q,1]*v[q,1])
                if tangent>1e-12 and normal_speed>0.:
                    drop=min(tangent,friction*normal_speed)
                    factor=(tangent-drop)/tangent
                    v[q,0]*=factor;v[q,1]*=factor
                count+=1
                if correction>maximum:maximum=correction
            continue

        nx=_sample_bilinear(gx,vv,u)
        ny=_sample_bilinear(gz,vv,u)
        length=math.sqrt(nx*nx+ny*ny)
        if length<1e-10:
            continue
        nx/=length;ny/=length
        correction=margin-distance
        x[q,0]+=nx*correction;x[q,1]+=ny*correction
        vn=v[q,0]*nx+v[q,1]*ny
        normal_speed=0.
        if vn<0:
            normal_speed=-vn
            v[q,0]-=vn*nx;v[q,1]-=vn*ny

        # Coulomb side-wall friction is tied to the removed normal impulse.
        # The previous fixed per-step multiplier exponentially damped even
        # perfectly wall-parallel flow and made the result timestep-dependent.
        tangent=math.sqrt(v[q,0]*v[q,0]+v[q,1]*v[q,1])
        if tangent>1e-12 and normal_speed>0.:
            drop=min(tangent,friction*normal_speed)
            factor=(tangent-drop)/tangent
            v[q,0]*=factor;v[q,1]*=factor
        count+=1
        if correction>maximum:maximum=correction
    return count,maximum


@njit(cache=True,inline='always')
def _enthalpy_temperature(H,p):
    cp,L,Ts,Tl,amb=p[6],p[7],p[8],p[9],p[10]
    h0=cp*(Ts-amb);h1=cp*(Tl-amb)+L
    if H<h0:return amb+H/cp
    if H>h1:return amb+(H-L)/cp
    return Ts+(H-h0)/(cp+L/(Tl-Ts))


@njit(cache=True)
def _mold_heat_transfer(x,J,H,mass,sdf,lo,extent,scale,center_z,wall_top,margin,
                        floor,band,conductance,mold_temperature,p,dt):
    """Resolution-stable effective thermal contact with the basalt mold.

    The sink is expressed per unit material mass using the MPM cell spacing as
    the characteristic contact thickness.  This avoids numerical-particle area
    inflation when source particles are subdivided for smoother inlet flux.
    """
    loss=0.;contacts=0
    h,w=sdf.shape
    rho=p[1];dx=p[0];cp=p[6];ambient=p[10]
    mold_H=cp*(mold_temperature-ambient)
    for q in range(len(x)):
        faces=0.
        if x[q,2]<=floor+band:
            faces+=1.
        if x[q,2]<=wall_top+margin+band:
            sx=x[q,0]/scale
            sz=x[q,1]/scale+center_z
            u=(sx-lo[0])/extent[0]*(w-1)
            vv=(sz-lo[2])/extent[2]*(h-1)
            distance=_sample_bilinear(sdf,vv,u)*scale
            if distance>=0.:
                if distance<=margin+band:faces+=1.
            elif x[q,2]<=wall_top+margin+band:
                faces+=1.
        if faces==0:continue
        T=_enthalpy_temperature(H[q],p)
        if T<=mold_temperature:continue
        specific_rate=conductance*faces*(T-mold_temperature)/(rho*dx)
        dH=specific_rate*dt
        available=max(0.,H[q]-mold_H)
        if dH>available:dH=available
        H[q]-=dH
        loss+=dH*mass[q]
        contacts+=1
    return loss,contacts


def apply_mold_contact(sim: LavaMPM,mold):
    return _mold_contact(sim.x,sim.v,mold['sdf'],mold['gx'],mold['gz'],
                         mold['lo'],mold['extent'],float(mold['stageScale']),
                         float(mold['sourceCenterZ']),float(mold['wallTop']),
                         float(mold['margin']),float(mold['friction']))


def advance_with_mold(sim: LavaMPM,duration: float,mold,source=None):
    if duration<0 or not math.isfinite(duration):
        raise ValueError('invalid duration')
    target=sim.time+duration;c=sim.config
    corrections=0;maximum=0.;injected=0;thermal_contacts=0;mold_loss=0.
    speed=float(np.linalg.norm(sim.v,axis=1).max())
    wave=math.sqrt((c.bulk_modulus+4*c.shear_modulus/3)/c.density)
    while target-sim.time>1e-12:
        if source is not None:
            added=_inject_due_source(sim,source,sim.time)
            injected+=added
            if added:speed=float(np.linalg.norm(sim.v,axis=1).max())
            cursor=int(source.get('cursor',0))
            next_release=float(source['releaseTime'][cursor]) if cursor<len(source['releaseTime']) else math.inf
        else:
            next_release=math.inf
        step_target=min(target,next_release)
        if step_target-sim.time<=1e-12:
            if source is not None:
                added=_inject_due_source(sim,source,next_release)
                injected+=added
                if added:speed=float(np.linalg.norm(sim.v,axis=1).max())
                continue
            break
        if sim.steps%12==0:
            speed=float(np.linalg.norm(sim.v,axis=1).max())
            compression=max(1.,float(sim.J.min())**-1.5)
            wave=math.sqrt((c.bulk_modulus+4*c.shear_modulus/3)/c.density)*compression
        dt=min(step_target-sim.time,c.max_dt,c.cfl*c.spacing/(wave+speed))
        sim.step(dt)
        n,d=apply_mold_contact(sim,mold)
        corrections+=int(n);maximum=max(maximum,float(d))
        q,tc=_mold_heat_transfer(sim.x,sim.J,sim.H,sim.mass,mold['sdf'],mold['lo'],mold['extent'],
          float(mold['stageScale']),float(mold['sourceCenterZ']),float(mold['wallTop']),
          float(mold['margin']),float(c.floor),float(mold['thermalBand']),
          float(mold['thermalConductance']),float(mold['moldTemperature']),sim.params,dt)
        sim.mold_conduction_loss+=float(q);mold_loss+=float(q);thermal_contacts+=int(tc)
    if source is not None:
        injected+=_inject_due_source(sim,source,sim.time)
    sim.validate()
    row=sim.metrics()
    row['moldContactCorrections']=corrections
    row['maxMoldCorrectionMeters']=maximum
    row['moldThermalContacts']=int(thermal_contacts)
    row['moldConductionLossThisAdvanceJ']=float(mold_loss)
    row['sourceParticlesInjectedThisAdvance']=int(injected)
    row['sourceParticlesRemaining']=int(len(source['releaseTime'])-source.get('cursor',0)) if source is not None else 0
    return row

