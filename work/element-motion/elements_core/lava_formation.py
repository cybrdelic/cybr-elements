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
    nozzle_bottom: float = .22
    nozzle_radius_main: float = .036
    nozzle_radius_small: float = .029
    main_nozzles: int = 3
    wall_margin_fraction: float = .22
    inlet_speed: float = .55
    initial_down_speed: float = .55
    skin_temperature: float = 1310.
    core_temperature: float = 1690.
    significant_component_pixels: int = 100

    def __post_init__(self):
        if self.stage_scale <= 0 or self.fill_height <= 0 or self.wall_height <= 0:
            raise ValueError('invalid formation scale')
        if self.main_nozzles < 1 or self.nozzle_radius_main <= 0 or self.nozzle_radius_small <= 0:
            raise ValueError('invalid nozzle configuration')
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
        radius=formation.nozzle_radius_main if component==components[0][0] else formation.nozzle_radius_small
        tangent=np.array([dirx[iy0,ix0],dirz[iy0,ix0]],np.float64)
        tangent/=max(float(np.linalg.norm(tangent)),1e-12)
        built=0;layer=0;start=len(positions)
        phase=1.7*inlet_index
        while built<total:
            growth=min(1.,layer/18.)
            effective_radius=radius*(.58+.42*growth)
            lattice=np.arange(-effective_radius,effective_radius+step*.5,step)
            disk=np.array([(a,b) for a in lattice for b in lattice if a*a+b*b<=effective_radius*effective_radius],np.float64)
            if len(disk)<4:
                # Preserve a narrow feed at coarse review spacing with a
                # deterministic center + four-point ring instead of silently
                # inflating the physical nozzle radius.
                rr=min(effective_radius*.62,step*.72)
                disk=np.array([[0.,0.],[rr,0.],[-rr,0.],[0.,rr],[0.,-rr]],np.float64)
            take=min(len(disk),total-built)
            wobble=np.array([.006*math.sin(phase+layer*.61),.0045*math.cos(phase*.7+layer*.47)])
            for a,b in disk[:take]:
                jitter=(rng.random(3)-.5)*step*.15
                z=formation.nozzle_bottom+layer*step
                positions.append([center[0]+wobble[0]+a+jitter[0],center[1]+wobble[1]+b+jitter[1],z+jitter[2]])
                radial=min(1.,math.hypot(a,b)/effective_radius)
                core=(1.-radial)**.55
                temperatures.append(formation.skin_temperature+
                                    (formation.core_temperature-formation.skin_temperature)*core)
                velocities.append([tangent[0]*formation.inlet_speed+.025*math.sin(layer*.43+phase),
                                   tangent[1]*formation.inlet_speed+.018*math.cos(layer*.37+phase),
                                   -(formation.initial_down_speed+.35*growth)])
            built+=take;layer+=1
        nozzle_rows.append({'component':int(component),'particles':total,'radius':radius,
                            'center':center.tolist(),'layers':layer,
                            'zMin':formation.nozzle_bottom,
                            'zMax':formation.nozzle_bottom+(layer-1)*step})

    positions=np.asarray(positions,np.float64)
    velocities=np.asarray(velocities,np.float64)
    temperatures=np.asarray(temperatures,np.float64)
    volumes=np.full(len(positions),step**3,np.float64)
    if positions[:,2].max()>lava.origin[2]+lava.spacing*(lava.shape[2]-6):
        raise RuntimeError('pour reservoir exceeds vertical transfer guard')

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
        nx=_sample_bilinear(gx,vv,u)
        ny=_sample_bilinear(gz,vv,u)
        length=math.sqrt(nx*nx+ny*ny)
        if length<1e-10:
            continue
        nx/=length;ny/=length
        correction=margin-distance
        x[q,0]+=nx*correction;x[q,1]+=ny*correction
        vn=v[q,0]*nx+v[q,1]*ny
        if vn<0:
            v[q,0]-=vn*nx;v[q,1]-=vn*ny
        tangent_scale=max(0.,1.-friction*.02)
        v[q,0]*=tangent_scale;v[q,1]*=tangent_scale
        count+=1
        if correction>maximum:maximum=correction
    return count,maximum


def apply_mold_contact(sim: LavaMPM,mold):
    return _mold_contact(sim.x,sim.v,mold['sdf'],mold['gx'],mold['gz'],
                         mold['lo'],mold['extent'],float(mold['stageScale']),
                         float(mold['sourceCenterZ']),float(mold['wallTop']),
                         float(mold['margin']),float(mold['friction']))


def advance_with_mold(sim: LavaMPM,duration: float,mold):
    if duration<0 or not math.isfinite(duration):
        raise ValueError('invalid duration')
    target=sim.time+duration;c=sim.config
    corrections=0;maximum=0.
    speed=float(np.linalg.norm(sim.v,axis=1).max())
    wave=math.sqrt((c.bulk_modulus+4*c.shear_modulus/3)/c.density)
    while target-sim.time>1e-12:
        if sim.steps%12==0:
            speed=float(np.linalg.norm(sim.v,axis=1).max())
            compression=max(1.,float(sim.J.min())**-1.5)
            wave=math.sqrt((c.bulk_modulus+4*c.shear_modulus/3)/c.density)*compression
        dt=min(target-sim.time,c.max_dt,c.cfl*c.spacing/(wave+speed))
        sim.step(dt)
        n,d=apply_mold_contact(sim,mold)
        corrections+=int(n);maximum=max(maximum,float(d))
    sim.validate()
    row=sim.metrics()
    row['moldContactCorrections']=corrections
    row['maxMoldCorrectionMeters']=maximum
    return row
