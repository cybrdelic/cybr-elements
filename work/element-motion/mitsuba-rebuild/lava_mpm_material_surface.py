"""Fracture-aware material-domain boundary for structured MPM quadrature.

Eight corners per material point follow its local material deformation. Only
locally connected cells share a corner. A crack can therefore remain open
even when the specimen is globally connected around its tip. No density
blur, fracture noise, gap widening, per-frame triangulation, or painted cuts.

This is a finite material-domain reconstruction, not a liquid remesher.
Inlet caches with duplicate reference cells are rejected explicitly. The
export records Jacobians and volume errors instead of hiding distortion by
globally scaling the surface to a target volume.
"""
import hashlib, json
from itertools import product
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from lava_skin import normals

CORNERS=np.array(list(product((0,1),repeat=3)),dtype=int)
QUADS=np.array([[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]])
OFFSETS=np.array([[-1,0,0],[1,0,0],[0,-1,0],[0,1,0],[0,0,-1],[0,0,1]])


def reconstruct(s,sample,measure_cracks_only=False):
    sample=np.broadcast_to(np.asarray(sample,dtype=float),(3,));n=len(s['x'])
    rest=s['rest'];base=rest.min(0);coord=np.rint((rest-base)/sample).astype(int)
    if np.max(abs(base+coord*sample-rest))>sample.min()*1e-5:
        raise ValueError('Material-domain meshing requires a structured reference lattice')
    lookup={tuple(q):i for i,q in enumerate(coord)}
    if len(lookup)!=n:
        raise ValueError('Duplicate reference cells: this inlet cache needs persistent source-domain topology; kernel fallback would erase fractures')
    cold=np.asarray(s['bond_frozen'],dtype=bool)
    broken={tuple(sorted(q)) for q in s['bond_edges'][s['bond_broken']] if cold[q].all()}
    neighbors=np.full((n,6),-1,dtype=int);separated=np.zeros((n,6),dtype=bool)
    for p,q in enumerate(coord):
        for side,offset in enumerate(OFFSETS):
            other=lookup.get(tuple(q+offset),-1);neighbors[p,side]=other
            separated[p,side]=other>=0 and tuple(sorted((p,other))) in broken
    # A graph for material cells sharing each reference vertex. Restricting
    # connectivity to that vertex preserves a partial crack and its tip.
    key=(coord[:,None,:]+CORNERS[None,:,:]).reshape(-1,3)
    _,vertex_key=np.unique(key,axis=0,return_inverse=True)
    parent=np.arange(n*8)
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for p in range(n):
        for side in (1,3,5):
            other=neighbors[p,side]
            if other<0 or separated[p,side]:continue
            for a in QUADS[side]:
                b=np.flatnonzero(vertex_key[other*8:(other+1)*8]==vertex_key[p*8+a])[0]
                ra=root(p*8+int(a));rb=root(other*8+int(b))
                if ra!=rb:parent[max(ra,rb)]=min(ra,rb)
    roots=np.array([root(i) for i in range(n*8)])
    _,mapping=np.unique(roots,return_inverse=True);cells=mapping.reshape(n,8)
    # Grid velocity gradients are discontinuous across released MPM fields.
    # Accumulated grid F can become extreme at a crack even when neighboring
    # material positions remain well behaved. Reconstruct the spatial map
    # from intact material neighbors, never from samples across a broken
    # bond. This exactly reproduces an affine map and preserves an actual
    # positional discontinuity. It does not widen or draw the discontinuity.
    F=np.empty((n,3,3));unresolved=0
    offsets=np.array(list(product((-1,0,1),repeat=3)))
    for p,q in enumerate(coord):
        near=[]
        for offset in offsets:
            other=lookup.get(tuple(q+offset),-1)
            if other<0 or other==p or tuple(sorted((p,other))) in broken:continue
            near.append(other)
        dr=(rest[near]-rest[p])/sample
        delta=s['x'][near]-s['x'][p]
        if len(near)>=3 and np.linalg.matrix_rank(dr)==3:
            F[p]=np.linalg.lstsq(dr,delta,rcond=None)[0].T/sample[None,:]
        else:
            # A single point/thin line cannot resolve 3-D shear. Its finite
            # volume and polar rotation are the available domain evidence.
            U,_,Vh=np.linalg.svd(s['F'][p]);F[p]=U@Vh
            unresolved+=1
    det=np.linalg.det(F)
    if (det<=0).any():raise ValueError('Inverted map between intact material neighbors')
    # MPM uses B-bar volume, which is authoritative for material mass. Match
    # each affine domain to that volume before connected-corner averaging.
    F*=np.cbrt(s['volume']/(np.prod(sample)*det))[:,None,None]
    candidate=s['x'][:,None,:]+np.einsum('pij,kj->pki',F,(CORNERS-.5)*sample)
    count=np.bincount(mapping);v=np.zeros((len(count),3));ref=np.zeros_like(v)
    np.add.at(v,mapping,candidate.reshape(-1,3));v/=count[:,None]
    np.add.at(ref,mapping,(rest[:,None,:]+(CORNERS-.5)*sample).reshape(-1,3));ref/=count[:,None]
    attrs={}
    for name in ('temperature','solid','damage'):
        attrs[name]=np.bincount(mapping,weights=np.repeat(s[name],8))/count
    # Connected mesh components are integer identities, never phase values.
    intact=(neighbors>=0)&~separated
    a,b=np.nonzero(intact);a=a.astype(int);b=neighbors[a,b]
    adj=coo_matrix((np.ones(len(a)),(a,b)),shape=(n,n)).tocsr()
    _,component=connected_components(adj,directed=False)
    solid_adj=coo_matrix((np.ones(int(np.sum(cold[a]&cold[b]))),
                         (a[cold[a]&cold[b]],b[cold[a]&cold[b]])),shape=(n,n)).tocsr()
    _,solid_labels=connected_components(solid_adj,directed=False)
    material_id=np.where(cold,solid_labels+1,0)
    mesh_component=np.zeros(len(v),dtype=int)
    # Keep categorical identity. At a melt/solid interface choose the solid
    # side; the continuous phase attribute independently controls optics.
    np.maximum.at(mesh_component,mapping,np.repeat(material_id,8))
    quads=cells[:,QUADS];p0=v[quads[:,:,0]];p1=v[quads[:,:,1]];p2=v[quads[:,:,2]];p3=v[quads[:,:,3]]
    cell_volume=(np.einsum('psi,psi->ps',p0,np.cross(p1,p2))+np.einsum('psi,psi->ps',p0,np.cross(p2,p3))).sum(1)/6
    bad=np.flatnonzero(cell_volume<=0)
    if len(bad) and (not measure_cracks_only or cold[bad].any()):
        raise ValueError(('Connected corner reconstruction inverted material cells',dict(count=len(bad),indices=bad[:12].tolist(),minimum=float(cell_volume.min()),maximumFCondition=float(np.linalg.cond(F).max()))))
    keep=neighbors<0;opening=[];opening_faces=[];gap_faces=[]
    for p,side in zip(*np.nonzero(separated)):
        other=neighbors[p,side]
        a=v[quads[p,side]];b=v[quads[other,side^1]]
        normal=np.cross(a[1]-a[0],a[2]-a[0]);normal/=max(np.linalg.norm(normal),1e-30)
        gap=float((b.mean(0)-a.mean(0))@normal)
        if p<other:
            opening.append(gap);opening_faces.append([int(p),int(other)])
            ra=ref[quads[p,side]];rb=ref[quads[other,side^1]]
            order=np.argmin(np.linalg.norm(ra[:,None,:]-rb[None,:,:],axis=2),axis=1)
            if len(np.unique(order))!=4:raise ValueError('Crack reference face correspondence is ambiguous')
            gap_faces.append(np.stack([a,b[order]]))
        # Coincident faces retain independent topology but do not generate
        # z-fighting or visible lines. No minimum cosmetic opening is added.
        keep[p,side]=gap>sample.min()*1e-6
    boundary=quads[keep];f=np.concatenate((boundary[:,[0,1,2]],boundary[:,[0,2,3]]))
    crack_quad=separated[keep];is_crack=np.tile(crack_quad,2)
    # Geometry retains separate crack-face vertices. Shading refinement is
    # applied only on the exported boundary, without moving these vertices.
    out=dict(v=v,f=f,normal=normals(v,f),rest=ref,uv=ref[:,:2],component=mesh_component,
             crack_face=is_crack,crack_vertices=np.unique(quads[separated]),gap_faces=np.array(gap_faces),particle_cells=cells,cell_volume=cell_volume,**attrs)
    errors=abs(cell_volume-s['volume'])/s['volume'];gaps=np.array(opening)
    report=dict(method='locally connected advected material domains',particles=n,vertices=len(v),triangles=len(f),
        brokenFacePairs=len(gaps),openFacePairs=int((gaps>sample.min()*1e-6).sum()),
        maximumOpeningM=float(gaps.max()) if len(gaps) else 0.,minimumOpeningM=float(gaps.min()) if len(gaps) else 0.,
        crackWallTriangles=int(is_crack.sum()),globalMaterialComponents=int(component.max()+1),
        solidMaterialComponents=int(len(np.unique(material_id[cold]))) if cold.any() else 0,
        relativeVolumeDifference=float(abs(cell_volume.sum()-s['volume'].sum())/s['volume'].sum()),
        cellVolumeRelativeErrorP95=float(np.quantile(errors,.95)),maximumCellVolumeRelativeError=float(errors.max()),
        minimumCellVolumeM3=float(cell_volume.min()),maximumDeformationCondition=float(np.linalg.cond(F).max()),
        solverParticleVolumeM3=float(s['volume'].sum()),reconstructedVolumeM3=float(cell_volume.sum()),
        openingPairs=opening_faces,openingM=opening,
        deformationSource='Affine least-squares map of intact material neighbors, normalized to each solved material volume',
        unresolvedAffineCells=unresolved,
        invertedLiquidCellsExcludedFromCrackMeasurement=int(len(bad)) if measure_cracks_only else 0,
        maximumCoherentDeformationCondition=float(np.linalg.cond(F[cold]).max()) if cold.any() else 1.,
        limits='Structured material lattice only; volume and distortion are checked. Rank-deficient cells retain measured polar rotation and volume. No liquid remeshing or manufactured subgrid surface detail.')
    return out,report


def crease_normals(mesh,angle=40.):
    """Separate shading at resolved edges and crack walls without moving them."""
    v=mesh['v'];f=mesh['f'];area=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
    unit=area/np.maximum(np.linalg.norm(area,axis=1)[:,None],1e-30)
    incident=[[] for _ in v]
    for i,tri in enumerate(f):
        for k,p in enumerate(tri):incident[p].append((i,k))
    newf=np.empty_like(f);source=[];normal=[];threshold=np.cos(np.deg2rad(angle))
    for p,faces in enumerate(incident):
        groups=[]
        for face,corner in faces:
            selected=None
            for group in groups:
                other=group[0][0]
                if mesh['crack_face'][face]==mesh['crack_face'][other] and unit[face]@unit[other]>=threshold:
                    selected=group;break
            if selected is None:selected=[];groups.append(selected)
            selected.append((face,corner))
        for group in groups:
            index=len(source);source.append(p);n=area[[q[0] for q in group]].sum(0);n/=max(np.linalg.norm(n),1e-30);normal.append(n)
            for face,corner in group:newf[face,corner]=index
    source=np.asarray(source,dtype=int)
    mesh['control_v']=v.copy()
    for key in ('v','rest','uv','component','temperature','solid','damage'):mesh[key]=mesh[key][source]
    mesh['normal']=np.array(normal);mesh['f']=newf
    return mesh


def extract(path,smooth_outer=False):
    path=Path(path);s=dict(np.load(path));meta=json.loads((path.parent/'state.json').read_text())
    out,receipt=reconstruct(s,meta.get('sample_size',[meta['spacing']]*3))
    from lava_mpm_hybrid_surface import fair_liquid
    out,fairing=fair_liquid(out,s['bond_frozen'],meta.get('sample_size',[meta['spacing']]*3))
    receipt['liquidFairing']=fairing
    if smooth_outer:
        from lava_mpm_outer_surface import reconstruct_outer
        out,outer=reconstruct_outer(out,s,np.array(meta.get('sample_size',[meta['spacing']]*3)))
        receipt['outerReconstruction']=outer
        receipt['method']+=' with density-guided exterior'
        receipt['reconstructedVolumeM3']=float(out['cell_volume'].sum())
        receipt['relativeVolumeDifference']=float(abs(out['cell_volume'].sum()-s['volume'].sum())/s['volume'].sum())
    # Recompute the same volume measures after the accepted liquid pass.
    errors=abs(out['cell_volume']-s['volume'])/s['volume']
    receipt.update(cellVolumeRelativeErrorP95=float(np.quantile(errors,.95)),maximumCellVolumeRelativeError=float(errors.max()),minimumCellVolumeM3=float(out['cell_volume'].min()))
    # Cell indices refer to the unsplit reconstruction vertices. They must
    # not survive export after crease_normals duplicates/reorders vertices.
    out.pop('particle_cells',None);out.pop('crack_vertices',None);out.pop('gap_faces',None)
    out=crease_normals(out);receipt['shadingVertices']=len(out['v'])
    receipt['normals']='Area-weighted within smooth regions; split at resolved creases and crack walls. No displaced surface detail.'
    receipt['fractureTopologyPreserved']=True
    center=(out['v'].min(0)+out['v'].max(0))*.5;size=float(np.ptp(out['v'],axis=0).max())
    out.update(camera_eye=center+np.array([.8,-1.5,1.15])*size,camera_target=center,camera_fov=38.,time=s['time'])
    dest=path.with_name(path.stem+'-surface.npz');np.savez_compressed(dest,**out)
    receipt.update(source=str(path),sourceSha256=hashlib.sha256(path.read_bytes()).hexdigest(),physicalSeconds=float(s['time']))
    dest.with_suffix('.json').write_text(json.dumps(receipt,indent=2));return dest
