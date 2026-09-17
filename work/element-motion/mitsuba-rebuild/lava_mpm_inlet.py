"""Nonzero inlet boundary and conservative material-source quadrature."""
import numpy as np
from scipy.sparse import coo_matrix


def thermal_boundary(xyz,area,cell_size,config):
    """Partition the density-interface area at the physical nozzle mouth.

    The enclosed pipe exchanges heat with its declared wall reservoir; it
    is not an exposed air surface. Linear nodal coverage spans one cell at
    the mouth. Both partitions sum to the original area, so heat exchanges
    cannot be counted twice. This remains a coarse boundary quadrature.
    """
    if 'pipe_end' not in config:raise ValueError('Thermal pipe needs its mouth position')
    cover=np.clip((config['pipe_end']-xyz[:,0])/cell_size[0]+.5,0.,1.)
    return area*(1-cover),area*cover


def profile(y,z,config):
    half=config['half_width'];height=config['height'];peak=config['peak_speed']
    return peak*np.maximum(0,1-(np.asarray(y)/half)**2)*np.maximum(0,4*np.asarray(z)/height*(1-np.asarray(z)/height))


def velocity_map(xyz,dx,labels,config,ground=True,ground_mask=None,cell_size=None):
    """Quadratic-spline Dirichlet inlet, with affine ghost reflection.

    At x=x_inlet, u=U. Upstream ghost velocities are 2U-u_mirror.
    The z=0 ground uses odd reflection. Their composition handles corners.
    Returns the linear map and nonzero lift, u = S*z + lift.
    """
    cell=np.full(3,dx) if cell_size is None else np.asarray(cell_size)
    plane=config['plane'];eps=min(cell)*1e-7
    # Quantize relative to a grid node, not world zero. With a half-cell
    # world offset, round(q/cell) aliases adjacent nodes (banker's rounding).
    anchor=xyz.min(axis=0)
    grounded=np.full(len(xyz),ground,dtype=bool) if ground_mask is None else ground&np.asarray(ground_mask,dtype=bool)
    # A split field may contain different attached-particle mass on opposite
    # sides of a ghost reflection. Boundary type belongs to the reflected
    # degree of freedom, not to either stencil's local mass fraction.
    # Close the mask over both reflections; unbonded hovering fields stay free.
    canonical=xyz.copy();canonical[:,0]=np.where(canonical[:,0]<plane,2*plane-canonical[:,0],canonical[:,0]);canonical[:,2]=abs(canonical[:,2])
    _,orbit=np.unique(np.c_[np.round((canonical-anchor)/cell).astype(int),labels],axis=0,return_inverse=True)
    orbit_bound=np.zeros(orbit.max()+1,dtype=bool);np.logical_or.at(orbit_bound,orbit,grounded);grounded=orbit_bound[orbit]
    interior=(xyz[:,0]>plane+eps)&((xyz[:,2]>eps)|~grounded)
    ii=np.flatnonzero(interior);col={int(j):i for i,j in enumerate(ii)}
    lookup={(*np.round((q-anchor)/cell).astype(int),int(labels[i])):i for i,q in enumerate(xyz)}
    if len(lookup)!=len(xyz):raise ValueError('Inlet grid-coordinate keys are not unique')
    rr=[];cc=[];vv=[];lift=np.zeros((len(xyz),3))
    for i,position in enumerate(xyz):
        target=position.copy();sign=1.;offset=np.zeros(3)
        if grounded[i] and target[2]<-eps:target[2]*=-1;sign=-1.
        prescribed=np.array([float(profile(target[1],target[2],config)),0,0])
        if target[0]<plane-eps:
            target[0]=2*plane-target[0];offset=sign*2*prescribed;sign*=-1
        if grounded[i] and abs(target[2])<=eps:
            lift[i]=0;continue
        if abs(target[0]-plane)<=eps:
            lift[i]=offset+sign*prescribed;continue
        j=lookup.get((*np.round((target-anchor)/cell).astype(int),int(labels[i])))
        if j is None or j not in col:raise RuntimeError(('Missing reflected inlet/ground material support',dict(node=i,position=position.tolist(),target=target.tolist(),label=int(labels[i]),grounded=bool(grounded[i]),mirror=j,mirrorGrounded=None if j is None else bool(grounded[j]))))
        lift[i]=offset
        for axis in range(3):rr.append(3*i+axis);cc.append(3*col[j]+axis);vv.append(sign)
    return coo_matrix((vv,(rr,cc)),shape=(len(xyz)*3,len(ii)*3)).tocsr(),lift.ravel()


def columns(spacing,dx,config):
    sample=np.broadcast_to(np.asarray(spacing),(3,));cell=np.broadcast_to(np.asarray(dx),(3,))
    yz=np.array(np.meshgrid(np.arange(-config['half_width']+sample[1]/2,config['half_width'],sample[1]),
                            np.arange(sample[2]/2,config['height'],sample[2]),indexing='ij')).reshape(2,-1).T
    # Match the prescribed spline profile, rather than injecting according
    # to a different analytic flux at the same boundary.
    q=yz/cell[1:];b=np.floor(q-.5).astype(int);f=q-b
    w=np.array([.5*(1.5-f)**2,.75-(f-1)**2,.5*(f-.5)**2])
    speed=np.zeros(len(yz))
    for i in range(3):
        for j in range(3):
            z=(b[:,1]+j)*cell[2]
            value=profile((b[:,0]+i)*cell[1],abs(z),config)*np.where(z<0,-1,1) if config.get('ground_profile',True) else profile((b[:,0]+i)*cell[1],z,config)
            speed+=w[i,:,0]*w[j,:,1]*value
    keep=speed>1e-10
    return yz[keep],speed[keep]


def emit(s,config,interval,seed=False):
    yz,speed=columns(s.sample_size,s.cell_size,config)
    if len(yz)==0:
        raise ValueError('Inlet profile is unresolved on this grid: its sampled flux is zero')
    x=np.c_[config['plane']+speed*interval/2,yz]
    v=np.zeros_like(x);v[:,0]=speed
    volume=np.prod(s.sample_size[1:])*speed*interval
    s.add_particles(x,v,np.full(len(x),config['temperature']),volume,source_kind='inlet')
    # Birth position is not a unique material coordinate: every emission
    # repeats the same physical inlet. Give each new layer a persistent
    # upstream reference cell, and retain its actual longitudinal extent
    # in F. This preserves geometry/identity through later crust formation.
    layer=int(s.ledger.get('inlet_reference_layers',0))
    s.rest[-len(x):]=np.c_[np.full(len(x),config['plane']-(layer+.5)*s.sample_size[0]),yz]
    s.F[-len(x):,0,0]=speed*interval/s.sample_size[0]
    s.ledger['inlet_reference_layers']=layer+1
    return dict(particles=len(x),mass=float(volume.sum()*s.material.density),volume=float(volume.sum()),quadratureFluxM3PerS=float(volume.sum()/interval))


def conduit_constraints(x,velocity,local,w,nodes,dx,dt,config):
    """Unilateral material-point contact against the inlet's rigid walls.

    Each row constrains interpolated velocity so the next point position
    cannot cross a wall. These are stationary external obstacles; their
    impulses are recorded separately from internal fragment contact.
    """
    if 'pipe_end' not in config:return coo_matrix((0,nodes*3)).tocsr(),np.zeros(0)
    inside=x[:,0]<config['pipe_end']-1e-10
    end_gap=x[:,0]-config['pipe_end']
    cross=np.minimum(config['half_width']-abs(x[:,1]),config['height']-x[:,2])
    if config.get('bottom_wall',False):cross=np.minimum(cross,x[:,2])
    if np.min(np.maximum(end_gap,cross))<-.25*dx:
        raise RuntimeError('Material starts too far outside the conduit')
    # At a slightly penetrated mouth corner, the nearest free region may
    # be downstream. A side-wall plane must not extend past the finite tube
    # and demand a large transverse correction when the end face is closer.
    side_region=inside&(end_gap<=cross)
    guard=.2*dx+dt*np.maximum(np.linalg.norm(velocity,axis=1),config['peak_speed'])
    rr=[];cc=[];vv=[];bound=[]
    walls=[(1,1,config['half_width']),(1,-1,-config['half_width']),(2,1,config['height'])]
    if config.get('bottom_wall',False):walls.append((2,-1,0.))
    for axis,sign,position in walls:
        gap=sign*(position-x[:,axis]);candidate=np.flatnonzero(side_region&(gap<guard))
        for p in candidate:
            row=len(bound);bound.append(gap[p]/dt)
            rr.extend([row]*27);cc.extend((local[p]*3+axis).tolist());vv.extend((sign*w[p]).tolist())
    # The solid surrounding the pipe opening has a downstream end face.
    # Omitting it allowed spreading lava to move backward behind the tube
    # mouth while outside its cross section, then start the next step deep
    # inside a side wall. Enforce that physical end face before penetration.
    future=x+dt*velocity
    outside=(abs(x[:,1])>config['half_width'])|(x[:,2]>config['height'])
    future_outside=(abs(future[:,1])>config['half_width'])|(future[:,2]>config['height'])
    if config.get('bottom_wall',False):
        outside|=x[:,2]<0;future_outside|=future[:,2]<0
    candidate=np.flatnonzero((outside|future_outside)&((end_gap>=-1e-10)|(end_gap>cross))&(end_gap<guard))
    for p in candidate:
        row=len(bound);bound.append(end_gap[p]/dt)
        rr.extend([row]*27);cc.extend((local[p]*3).tolist());vv.extend((-w[p]).tolist())
    return coo_matrix((vv,(rr,cc)),shape=(len(bound),nodes*3)).tocsr(),np.array(bound)


def conduit_gap(x,config):
    """Positive in the opening or downstream of the solid pipe end."""
    cross=np.minimum(config['half_width']-abs(x[:,1]),config['height']-x[:,2])
    if config.get('bottom_wall',False):cross=np.minimum(cross,x[:,2])
    return np.maximum(x[:,0]-config['pipe_end'],cross)


def solid_ground_constraints(x,volume,frozen,velocity,local,w,nodes,dx,dt,acceleration=(0,0,-9.81),radius=None):
    """Finite particle-domain floor contact; no remote Dirichlet pinning.

    Solid domains use their half cube width as a contact radius. This remains
    a particle-spacing boundary approximation, not exact mesh contact.
    """
    gap=x[:,2]-(.5*np.cbrt(volume) if radius is None else radius)
    guard=.2*dx+dt*np.linalg.norm(velocity,axis=1)+dt*dt*np.linalg.norm(acceleration)
    points=np.flatnonzero(frozen&(gap<guard))
    rows=np.repeat(np.arange(len(points)),27);columns=(local[points]*3+2).ravel();values=-w[points].ravel()
    return coo_matrix((values,(rows,columns)),shape=(len(points),nodes*3)).tocsr(),gap[points]/dt
