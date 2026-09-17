"""Declared fractured-crust initial condition and embedded solid boundaries.

Initial clasts are geometry, not fracture predictions. Their subsequent motion
comes exclusively from MPM. An affine fit embeds each stiff clast's boundary;
fit residual and volume drift are measured rather than hidden by re-sculpting.
"""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import map_coordinates,gaussian_filter
from skimage.measure import marching_cubes
from lava_mpm import ROOT,MPM,block
from lava_mpm_fed_run import save
from lava_mpm_inlet import profile
from lava_mpm_surface import fields,image_surface
from lava_skin import normals

SEEDS=np.array([[-.036,-.014],[.003,-.027],[.031,-.007],[-.027,.024],[.004,.014],[.045,.027]])
_NOISE=None
_PORES=None


def irregularity(p):
    global _NOISE
    if _NOISE is None:
        rng=np.random.default_rng(87016);raw=rng.normal(size=(96,96,96))
        _NOISE=[]
        for sigma in (9.,2.4,.8):
            n=gaussian_filter(raw,sigma,mode='wrap');_NOISE.append(n/n.std())
    coord=(p+.10).T/.2*96
    return [map_coordinates(n,coord,order=1,mode='wrap') for n in _NOISE]


def shape(p):
    global _PORES
    x,y,z=p.T
    # Centimetre relief and small fracture-face irregularity are the initial
    # solid boundary, shared by volume sampling and boundary extraction.
    r2=(x/.060)**2+(y/.043)**2
    broad,meso,fine=irregularity(p)
    top=.032-.008*r2+.0047*broad+.0020*meso+.00035*fine
    bottom=.010+.0012*broad
    outside=(1-r2+.13*broad)*.021
    planar=(np.sum(SEEDS**2,axis=1)[None,:]-2*p[:,:2]@SEEDS.T)
    closest=np.argmin(planar,axis=1)
    distances=np.empty((len(p),len(SEEDS)))
    for j in range(len(SEEDS)):
        others=np.arange(len(SEEDS))!=j
        margin=(planar[:,others]-planar[:,j,None])/(2*np.linalg.norm(SEEDS[others]-SEEDS[j],axis=1))
        local_top=top+np.array([.001,.004,-.002,.007,0,-.004])[j]
        distances[:,j]=np.minimum.reduce([margin.min(1)-.0015+.0011*meso+.0003*fine,local_top-z,z-bottom,outside])
    # Pre-existing vesicles in the declared solid volume. A truncated heavy
    # tail gives a few millimetre cavities among many small ones. These are
    # not a claim that gas nucleation or pore formation was simulated.
    if _PORES is None:
        rng=np.random.default_rng(52931);centers=rng.uniform([-.072,-.052,.012],[.066,.054,.048],(780,3))
        radius=np.minimum(.0036,.00075/(1-rng.uniform(0,.97,780))**(1/1.55))
        _PORES=(cKDTree(centers),radius)
    tree,radius=_PORES
    for begin in range(0,len(p),160000):
        end=min(len(p),begin+160000);distance,near=tree.query(p[begin:end],k=12)
        void=np.min(distance-radius[near],axis=1)
        distances[begin:end]=np.minimum(distances[begin:end],void[:,None])
    return distances,top,outside,closest


def volume(v,f):return abs(float(np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))/6))


def initial(name):
    folder=ROOT/name
    if (folder/'state.npz').exists():raise RuntimeError('Initial state already exists; never reset an evolved cache')
    folder.mkdir(parents=True,exist_ok=True)
    spacing=.005;dx=.01
    points=block([-.08,-.065,0],[.08,.065,.06],spacing)
    sdf,top,outer,nearest=shape(points)
    cold=sdf.max(1)>0
    fluid=(outer>0)&(points[:,2]<np.minimum(.016,top))&~cold
    keep=cold|fluid;points=points[keep];cold=cold[keep];nearest=nearest[keep]
    labels=np.where(cold,sdf[keep].argmax(1)+1,0)
    temperature=np.where(cold,890.+150*np.clip((.029-points[:,2])/.02,0,1),1450.)
    config=dict(plane=-.09,half_width=.015,height=.015,peak_speed=.06,temperature=1450.,pipe_end=-.075)
    channel=block([config['plane'],-.015,0],[-.05,.015,.015],spacing)
    dd,_=cKDTree(points).query(channel);channel=channel[dd>=spacing*.98]
    points=np.r_[points,channel];temperature=np.r_[temperature,np.full(len(channel),1450.)];labels=np.r_[labels,np.zeros(len(channel),int)]
    s=MPM(points,spacing,dx,temperature=temperature,origin=[-.11,-.09,-.02],shape=[30,20,16])
    s.v[-len(channel):,0]=profile(channel[:,1],channel[:,2],config)
    s.connectivity.frozen=labels>0
    edges=cKDTree(points).query_pairs(spacing*1.82,output_type='ndarray')
    edges=edges[(labels[edges[:,0]]==labels[edges[:,1]])&(labels[edges[:,0]]>0)]
    s.connectivity.edges=edges;s.connectivity.broken=np.zeros(len(edges),bool);s.connectivity.labels=labels.copy()
    # Explicit high-resolution clast boundaries; no render-only crack masks.
    fine_dx=.0007;lo=np.array([-.085,-.070,.003]);hi=np.array([.080,.065,.060])
    grid_shape=np.ceil((hi-lo)/fine_dx).astype(int)+1
    q=lo+np.array(np.unravel_index(np.arange(np.prod(grid_shape)),grid_shape)).T*fine_dx
    sdf,_,_,_=shape(q)
    meshes={};measures=[]
    for label in range(1,7):
        field=sdf[:,label-1].reshape(grid_shape)
        if max(field[0].max(),field[-1].max(),field[:,0].max(),field[:,-1].max(),field[:,:,0].max(),field[:,:,-1].max())>=0:raise RuntimeError('Initial boundary is clipped by its extraction domain')
        v,f,_,_=marching_cubes(field,0,spacing=(fine_dx,)*3);v+=lo
        signed=np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))/6
        if signed<0:f=f[:,[0,2,1]]
        target=volume(v,f);ix=labels==label
        # Subcell volume quadrature: each clast's particle weights integrate
        # the same closed boundary used for its optical surface.
        s.volume[ix]=target/ix.sum();s.mass[ix]=s.material.density*s.volume[ix]
        meshes[f'v{label}']=v;meshes[f'f{label}']=f
        measures.append(dict(label=label,particles=int(ix.sum()),volume=target,triangles=len(f)))
    s.initial_mass=float(s.mass.sum());s.initial_energy=float(s.mass@s.h)
    s.ledger['initial_kinetic']=float(.5*np.sum(s.mass*np.sum(s.v*s.v,axis=1)))
    np.savez_compressed(folder/'initial-boundaries.npz',**meshes,labels=labels,rest=s.rest)
    period=spacing/config['peak_speed']
    setup=dict(startTime=0.,config=config,period=period,nextEmission=period,emissions=0,
               description='Six initially fractured cold basalt clasts resting in molten lava. Initial cracks are prescribed geometry, NOT generated fracture history. All subsequent velocities, contact, heating and incoming source material are solved by MPM.',
               initialClasts=measures,initialHotK=1450.,initialColdK=[890.,1040.],boundaryResolutionM=fine_dx,porosity='780 prescribed spherical vesicle candidates; radius 0.75–3.6 mm, truncated Pareto exponent 1.55. Mesh volume sets particle mass. Pore formation is not simulated.',
               initialBoundarySha256=hashlib.sha256((folder/'initial-boundaries.npz').read_bytes()).hexdigest(),initializerSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    save(s,folder,setup)
    print(json.dumps(dict(run=name,particles=len(s.x),mass=s.initial_mass,clasts=measures,initialCondition=setup['description'])))


def surface(name,frame):
    folder=ROOT/name;a=dict(np.load(folder/(frame+'.npz')));base=np.load(folder/'initial-boundaries.npz');meta=json.loads((folder/'state.json').read_text())
    count=len(base['labels']);initial_labels=base['labels'];rest=base['rest']
    vertices=[];faces=[];temps=[];phases=[];damages=[];components=[];reports=[]
    for label in range(1,7):
        ix=np.flatnonzero(initial_labels==label);r=rest[ix];x=a['x'][ix]
        design=np.c_[r-r.mean(0),np.ones(len(r))];fit=np.linalg.lstsq(design,x,rcond=None)[0]
        residual=np.linalg.norm(design@fit-x,axis=1);worst=float(residual.max())
        if worst>meta['spacing']*.2:raise RuntimeError('Embedded clast boundary is no longer accurate; refine its kinematic map')
        if a['solid'][ix].min()<.85:raise RuntimeError('Embedded rigid crust remelted; switch to a deformable reconstruction')
        v0=base[f'v{label}'];f=base[f'f{label}'];v=np.c_[v0-r.mean(0),np.ones(len(v0))]@fit
        distances,near=cKDTree(r).query(v0,k=min(8,len(r)));w=1/np.maximum(distances,.001)**2;w/=w.sum(1)[:,None]
        t=np.sum(w*a['temperature'][ix][near],axis=1);solid=np.sum(w*a['solid'][ix][near],axis=1);damage=np.sum(w*a['damage'][ix][near],axis=1)
        goal=float(a['volume'][ix].sum());measured=volume(v,f)
        reports.append(dict(label=label,affineFitMaxM=worst,volumeDifference=abs(measured-goal)/goal,centroidDisplacementM=(x.mean(0)-r.mean(0)).tolist()))
        faces.append(f+sum(len(vv) for vv in vertices));vertices.append(v);temps.append(t);phases.append(solid);damages.append(damage);components.append(np.full(len(v),label))
    # Independently reconstruct the free melt. It is not allowed to bridge
    # distinct clasts or average their cold optical temperature with hot melt.
    melt=np.r_[initial_labels==0,np.ones(len(a['x'])-count,bool)]
    state={k:a[k][melt] for k in ('x','volume','temperature','solid','damage')}
    lo,dx,field=fields(state,meta['spacing']*.55);density=field['density'];target=state['volume'].sum();left=.015;right=density.max()*.95
    for _ in range(13):
        level=(left+right)/2;v,f,_,_=marching_cubes(density,level,spacing=tuple(dx));v+=lo
        measured=volume(v,f)
        if measured>target:left=level
        else:right=level
    if np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))<0:f=f[:,[0,2,1]]
    faces.append(f+sum(len(vv) for vv in vertices));vertices.append(v)
    for field_name,out in [('temperature',temps),('solid',phases),('damage',damages)]:out.append(map_coordinates(field[field_name],((v-lo)/dx).T,order=1,mode='nearest'))
    components.append(np.zeros(len(v)))
    v=np.concatenate(vertices);f=np.concatenate(faces);center=(v.min(0)+v.max(0))*.5;size=float(np.ptp(v,axis=0).max())
    eye=center+np.array([.25,-1.6,1.8])*size
    output=folder/(frame+'-surface.npz')
    np.savez_compressed(output,v=v,f=f,normal=normals(v,f),uv=v[:,:2],rest=v.copy(),temperature=np.concatenate(temps),solid=np.concatenate(phases),damage=np.concatenate(damages),component=np.concatenate(components),camera_eye=eye,camera_target=center,camera_fov=38.,time=a['time'])
    receipt=dict(source=str(folder/(frame+'.npz')),sourceSha256=hashlib.sha256((folder/(frame+'.npz')).read_bytes()).hexdigest(),
                 method='Embedded initial clast boundaries with measured affine fits to MPM material displacement; conservative free-melt kernel reconstruction',clasts=reports,meltVolumeDifference=float(abs(measured-target)/target),
                 limits='Initial cracks and subgrid surface relief are specified initial geometry. No simulated crack-formation claim. Per-clast affine surface approximation; melt/solid kernel overlap at unresolved interfaces remains possible.')
    output.with_suffix('.json').write_text(json.dumps(receipt,indent=2));picture=image_surface(output)
    print(json.dumps(dict(surface=str(output),diagnostic=str(picture),maxFitErrorM=max(q['affineFitMaxM'] for q in reports),maxVolumeDifference=max(q['volumeDifference'] for q in reports))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='fractured-feed-14');p.add_argument('--init',action='store_true');p.add_argument('--frame',default='state');a=p.parse_args()
    if a.init:initial(a.name)
    surface(a.name,a.frame)
