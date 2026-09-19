"""Fixed-world-lattice material-point surface and advected optical attributes.

The final *smoothed and floor-constrained* mesh is tested against the current
MPM particle volume. This is a global representation check, not a local fluid
conservation proof. No per-frame randomly shifted lattice is used.
"""
from __future__ import annotations
import numpy as np
from numba import njit
from scipy.ndimage import gaussian_filter,map_coordinates
from skimage.measure import marching_cubes


@njit(cache=True)
def _splat(positions,volumes,values,origin,h,shape):
    density=np.zeros(shape,np.float32)
    attrs=np.zeros((*shape,values.shape[1]),np.float32)
    for p in range(len(positions)):
        c=(positions[p]-origin)/h
        i=np.floor(c).astype(np.int64);f=c-i
        for a in range(2):
            for b in range(2):
                for d in range(2):
                    w=(f[0] if a else 1-f[0])*(f[1] if b else 1-f[1])*(f[2] if d else 1-f[2])*volumes[p]/h**3
                    ii,jj,kk=i[0]+a,i[1]+b,i[2]+d
                    density[ii,jj,kk]+=w
                    for v in range(values.shape[1]):attrs[ii,jj,kk,v]+=w*values[p,v]
    return density,attrs


def mesh_volume(v,f):
    p=v-v.mean(0)
    return float(np.einsum('ij,ij->i',p[f[:,0]],np.cross(p[f[:,1]],p[f[:,2]])).sum()/6)


def vertex_normals(v,f):
    n=np.zeros_like(v)
    fn=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
    for col in range(3):
        for dim in range(3):n[:,dim]+=np.bincount(f[:,col],weights=fn[:,dim],minlength=len(v))
    n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-30)
    return n


def smooth_mesh(v,f,passes=2):
    edges=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]])
    edges=np.concatenate([edges,edges[:,::-1]])
    degree=np.bincount(edges[:,0],minlength=len(v))
    for _ in range(passes):
        for rate in (.38,-.39):
            avg=np.column_stack([np.bincount(edges[:,0],weights=v[edges[:,1],d],minlength=len(v)) for d in range(3)])
            avg/=np.maximum(degree,1)[:,None]
            v=v+rate*(avg-v)
    return v


def wall_contact_heights(height,wall_cell):
    """Monotone C1 conformance inside the wall kernel's two-cell support.

    The subcell contact core occupies 0.75 cell. Outside two cells the mapping
    is exactly identity. This is a specified reconstruction boundary rule,
    not a physical displacement or a claim of subcell solver resolution.
    """
    if wall_cell<=0:raise ValueError('Positive wall cell required')
    h=np.maximum(np.asarray(height,dtype=np.float64),0.)
    a=.75*wall_cell;b=2.*wall_cell;length=b-a
    t=np.clip((h-a)/length,0.,1.)
    mapped=(3*b-length)*t*t+(length-2*b)*t*t*t
    return np.where(h>=b,h,mapped)


def _sample_mold_xy(mold,xy):
    xy=np.asarray(xy,np.float64)
    scale=float(mold['stageScale']);center=float(mold['sourceCenterZ'])
    lo=np.asarray(mold['lo'],np.float64);extent=np.asarray(mold['extent'],np.float64)
    sdf=np.asarray(mold['sdf'],np.float64)
    sx=xy[...,0]/scale
    sy=xy[...,1]/scale+center
    u=(sx-lo[0])/extent[0]*(sdf.shape[1]-1)
    v=(sy-lo[2])/extent[2]*(sdf.shape[0]-1)
    coords=np.vstack([v.ravel(),u.ravel()])
    d=map_coordinates(sdf,coords,order=1,mode='nearest').reshape(u.shape)*scale
    if 'gx' in mold and 'gz' in mold:
        gx=map_coordinates(np.asarray(mold['gx'],np.float64),coords,order=1,mode='nearest').reshape(u.shape)
        gy=map_coordinates(np.asarray(mold['gz'],np.float64),coords,order=1,mode='nearest').reshape(u.shape)
    else:
        gx=np.zeros_like(d);gy=np.zeros_like(d)
    return d,gx,gy


def _mask_density_against_mold(density,origin,spacing,mold):
    """Prevent particle-kernel smoothing from leaking through solid glyph walls."""
    if mold is None:return density
    nx,ny,nz=density.shape
    xs=origin[0]+np.arange(nx)*spacing
    ys=origin[1]+np.arange(ny)*spacing
    xx,yy=np.meshgrid(xs,ys,indexing='ij')
    d,_,_=_sample_mold_xy(mold,np.stack([xx,yy],axis=-1))
    margin=float(mold.get('margin',0.))
    wall_top=float(mold['wallTop'])
    # Keep a sub-cell transition so marching cubes terminates on the cavity
    # boundary instead of producing a gap, but never allow density deep inside
    # the solid mold.
    # d==0 is the physical cavity wall and must remain a valid fluid
    # boundary. Fade only a small distance *inside the solid* so we do not
    # carve artificial clearance out of narrow letter strokes.
    width=max(spacing*.14,margin*.20,1e-6)
    gate=np.clip((d+width)/width,0.,1.)
    gate=gate*gate*(3.-2.*gate)
    zs=origin[2]+np.arange(nz)*spacing
    below=zs<=wall_top+max(margin,spacing*.10)
    result=density.copy()
    result[:,:,below]*=gate[:,:,None]
    return result


def _constrain_vertices_to_mold(v,mold,spacing):
    if mold is None:return v
    v=np.asarray(v,np.float64).copy()
    margin=float(mold.get('margin',0.));wall_top=float(mold['wallTop'])
    d,gx,gy=_sample_mold_xy(mold,v[:,:2])
    active=v[:,2]<=wall_top+max(margin,spacing*.18)
    bad=active&(d<0.)
    if np.any(bad):
        length=np.maximum(np.hypot(gx[bad],gy[bad]),1e-12)
        correction=(-d[bad]+spacing*.025)
        v[bad,0]+=gx[bad]/length*correction
        v[bad,1]+=gy[bad]/length*correction
    return v


def reconstruct(snapshot:dict,*,spacing=.006,world_origin=(-.896,-.32,0.),floor=.032,volume_tolerance=3e-4,contact_band=0.,mold=None):
    x=np.asarray(snapshot['positions'],np.float64)
    volumes=np.asarray(snapshot['particleVolume']*snapshot['volumeRatio'],np.float64)
    if len(x)==0 or np.any(volumes<=0) or not np.isfinite(x).all():raise ValueError('Invalid particles')
    reference=np.array(world_origin,np.float64)
    low=np.floor((x.min(0)-reference)/spacing).astype(int)-6
    high=np.ceil((x.max(0)-reference)/spacing).astype(int)+6
    origin=reference+low*spacing;shape=tuple((high-low+1).tolist())
    values=np.column_stack([snapshot['temperature'],snapshot['damage'],snapshot['rest']]).astype(np.float32)
    density,attrs=_splat(x,volumes,values,origin,spacing,shape)
    density=gaussian_filter(density,.72 if mold is not None else .85,mode='constant')
    # Attribute normalization must use the unmasked particle-support density.
    # The mold mask is a geometric solid constraint, not missing thermal data.
    attribute_density=density.copy()
    for c in range(values.shape[1]):
        attrs[...,c]=gaussian_filter(attrs[...,c],.85,mode='constant')/np.maximum(attribute_density,1e-14)
    density=_mask_density_against_mold(density,origin,spacing,mold)
    target=float(volumes.sum())
    lowlevel=.025;highlevel=float(density.max())*.985
    chosen=None
    for _ in range(16):
        level=(lowlevel+highlevel)*.5
        v,f,_,_=marching_cubes(density,level=level,spacing=(spacing,)*3,allow_degenerate=False)
        v=np.asarray(v,np.float64)+origin;f=np.asarray(f,np.int32)
        raw=mesh_volume(v,f)
        if raw<0:f=f[:,[0,2,1]];raw=-raw
        chosen=(v,f,level,raw)
        if abs(raw-target)/target<.0015:break
        if raw>target:lowlevel=level
        else:highlevel=level
    v,f,level,raw=chosen
    coords=((v-origin)/spacing).T
    optical=np.column_stack([map_coordinates(attrs[...,c],coords,order=1,mode='nearest') for c in range(values.shape[1])])
    # A normalized positive particle kernel cannot create state outside the
    # particle extrema. Bound rare near-zero-support interpolation excursions
    # to that physically admissible convex range.
    state_min=values.min(axis=0);state_max=values.max(axis=0)
    optical=np.minimum(np.maximum(optical,state_min[None,:]),state_max[None,:])
    v=smooth_mesh(v,f,passes=1 if mold is not None else 2)
    v=_constrain_vertices_to_mold(v,mold,spacing)
    height=np.maximum(v[:,2]-floor-.00005,0.)
    active=contact_band>0 and float(x[:,2].min())<=floor+2.5*contact_band
    if active:
        corrected=wall_contact_heights(height,contact_band)
        contact=corrected==0.
        contact_displacement=float(np.max(height-corrected))
        v[:,2]=floor+.00005+corrected
    else:
        contact=np.zeros(len(v),bool);contact_displacement=0.
        v[:,2]=np.maximum(v[:,2],floor+.00005)
    before=mesh_volume(v,f);normals=vertex_normals(v,f)
    def offset_volume(delta):
        candidate=v+normals*delta
        candidate[:,2]=np.maximum(candidate[:,2],floor+.00005)
        candidate[contact,2]=floor+.00005
        candidate=_constrain_vertices_to_mold(candidate,mold,spacing)
        return candidate,mesh_volume(candidate,f)
    a=-spacing*.4;b=spacing*.4
    va,vola=offset_volume(a);vb,volb=offset_volume(b)
    for _ in range(2):
        if vola<=target<=volb:break
        a*=2;b*=2;va,vola=offset_volume(a);vb,volb=offset_volume(b)
    if not vola<=target<=volb:
        raise RuntimeError(f'Meshing correction is too large: {vola}, {target}, {volb}')
    delta=0.
    for _ in range(28):
        delta=.5*(a+b);result,final=offset_volume(delta)
        if abs(final-target)/target<volume_tolerance*.5:break
        if final>target:b=delta
        else:a=delta
    result=result.astype(np.float32);final=mesh_volume(result.astype(np.float64),f)
    relative=abs(final-target)/target
    effective_tolerance=max(volume_tolerance,2e-3) if mold is not None else volume_tolerance
    if relative>effective_tolerance:raise RuntimeError(f'Final encoded volume error: {relative}')
    if not np.isfinite(optical).all():raise RuntimeError('Invalid surface attributes')
    return {'vertices':result,'faces':f,'temperature':optical[:,0],'damage':np.clip(optical[:,1],0,1),'rest':optical[:,2:5]}, {
        'vertices':len(result),'triangles':len(f),'spacing':spacing,'origin':origin.tolist(),'gridShape':shape,
        'level':level,'targetVolumeM3':target,'rawVolumeM3':raw,'smoothedVolumeM3':before,
        'finalVolumeM3':final,'finalVolumeRelativeError':relative,'volumeToleranceUsed':effective_tolerance,'normalCorrectionMeters':delta,
        'minimumFloorClearanceMeters':float(result[:,2].min()-floor),
        'contactVertices':int(contact.sum()),'physicsWallBandMeters':contact_band,'conformanceSupportMeters':2*contact_band,
        'maximumWallConformanceMeters':contact_displacement,'attributeTransport':'sample on particle-supported isosurface; carry through geometric corrections',
        'temperatureMinK':float(optical[:,0].min()),'temperatureMaxK':float(optical[:,0].max()),
        'moldConstrained':bool(mold is not None),
        'frameTime':float(snapshot['time'])}
