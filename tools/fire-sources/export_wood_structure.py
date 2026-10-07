"""Partition the approved tree into rigid beam-owned pieces without simplification.

Default is PRE-FLIGHT ONLY. --out writes private companion assets, never changes
the approved source. Every source triangle, position, normal, UV and material is
preserved; only shared seam vertices are duplicated. Closed interface loops get
separate interior caps, hidden while their owner pieces have the same pose.
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT/'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/objects/forest-tree'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def make_graph(nodes,parent,radius,density=495,strength=65e6):
    """Same layout as wood-structure.js; SI properties use MODEL metre units."""
    n=len(parent); static=np.zeros((n,16),np.float32); depth=np.zeros(n,np.uint32)
    if n==0 or parent[0]!=-1 or np.any(parent[1:]<0) or np.any(parent[1:]>=np.arange(1,n)):
        raise ValueError('Graph must be rooted and parent-before-child')
    mass=np.zeros(n,np.float64); weighted=np.zeros((n,3),np.float64)
    bounds=np.zeros((n,8),np.float32)
    for i in range(n):
        p=int(parent[i]);axis=nodes[i]-nodes[p] if p>=0 else np.array([0,1,0]);length=np.linalg.norm(axis) if p>=0 else 0
        if p>=0 and length<1e-8:raise ValueError('Zero length beam')
        axis=axis/max(np.linalg.norm(axis),1e-20);depth[i]=depth[p]+1 if p>=0 else 0
        m=np.pi*radius[i]**2*length*density; mass[i]=m
        midpoint=(nodes[i]+nodes[p])*.5 if p>=0 else nodes[i];weighted[i]=midpoint*m
        static[i]=[*nodes[i],p,*axis,radius[i],m,m,length,float(p<0),*nodes[i],strength]
        bounds[i,:3]=np.minimum(nodes[i],nodes[p] if p>=0 else nodes[i])-radius[i]
        bounds[i,4:7]=np.maximum(nodes[i],nodes[p] if p>=0 else nodes[i])+radius[i]
    for i in range(n-1,0,-1):
        p=parent[i];mass[p]+=mass[i];weighted[p]+=weighted[i]
        bounds[p,:3]=np.minimum(bounds[p,:3],bounds[i,:3]);bounds[p,4:7]=np.maximum(bounds[p,4:7],bounds[i,4:7])
    static[:,9]=mass;static[:,12:15]=np.divide(weighted,mass[:,None],out=nodes.astype(np.float64).copy(),where=mass[:,None]>0)
    return static,bounds,int(depth.max())

def closest_beams(points,nodes,parent,radius,k=24):
    edges=np.flatnonzero(parent>=0);a=nodes[parent[edges]];b=nodes[edges];ab=b-a
    length2=np.maximum(np.sum(ab*ab,axis=1),1e-20);tree=cKDTree((a+b)*.5)
    result=np.empty(len(points),np.uint32)
    for start in range(0,len(points),32768):
        q=points[start:start+32768];_,idx=tree.query(q,k=min(k,len(edges)),workers=1)
        if idx.ndim==1:idx=idx[:,None]
        ap=q[:,None,:]-a[idx];t=np.clip(np.sum(ap*ab[idx],axis=2)/length2[idx],0,1)
        distance=np.linalg.norm(ap-ab[idx]*t[:,:,None],axis=2)-radius[edges[idx]]*.35
        result[start:start+len(q)]=edges[idx[np.arange(len(q)),np.argmin(distance,axis=1)]]
    return result

def component_owners(vertices,faces,nodes,parent,radius):
    """A whole leaf/branch-litter component stays on one beam, never stretches."""
    used,inverse=np.unique(faces.reshape(-1),return_inverse=True);f=inverse.reshape(-1,3)
    rows=np.concatenate((f[:,0],f[:,1],f[:,2]));cols=np.concatenate((f[:,1],f[:,2],f[:,0]))
    graph=coo_matrix((np.ones(len(rows),np.uint8),(rows,cols)),shape=(len(used),len(used))).tocsr()
    count,labels=connected_components(graph,directed=False)
    centers=np.zeros((count,3),np.float64);weights=np.bincount(labels,minlength=count)
    for axis in range(3):centers[:,axis]=np.bincount(labels,weights=vertices[used,axis],minlength=count)/np.maximum(weights,1)
    return closest_beams(centers,nodes,parent,radius)[labels[f[:,0]]],count

def partition_mesh(vertices,faces,triangle_owner):
    keys=(np.repeat(triangle_owner,3).astype(np.uint64)<<32)|faces.reshape(-1).astype(np.uint64)
    unique,inverse=np.unique(keys,return_inverse=True)
    source_vertex=(unique&0xffffffff).astype(np.uint32);owners=(unique>>32).astype(np.uint32)
    return vertices[source_vertex],inverse.astype(np.uint32).reshape(-1,3),owners,source_vertex

def interior_caps(vertices,faces,owner):
    # Weld identical rest coordinates for edge topology; UV/normal seams remain
    # untouched in the visible mesh. No approximate spatial weld is used.
    points,weld=np.unique(vertices[:,:3],axis=0,return_inverse=True);f=weld[faces]
    starts=np.concatenate((f[:,0],f[:,1],f[:,2]));ends=np.concatenate((f[:,1],f[:,2],f[:,0]));own=np.tile(owner,3)
    keys=(np.minimum(starts,ends).astype(np.uint64)<<32)|np.maximum(starts,ends).astype(np.uint64)
    order=np.argsort(keys,kind='stable');sortedkeys=keys[order]
    at=np.flatnonzero(np.r_[True,sortedkeys[1:]!=sortedkeys[:-1]]);counts=np.diff(np.r_[at,len(order)])
    # Cancel opposite directed edges WITHIN each owner. This also retains
    # original open boundaries and nonmanifold remainder edges, keeping every
    # owner's boundary balanced. Restricting to two-face global edges left
    # dangling paths at the approved source's 33 nonmanifold seams.
    bypart=np.lexsort((own,keys));groupkey=keys[bypart];groupowner=own[bypart]
    ga=np.flatnonzero(np.r_[True,(groupkey[1:]!=groupkey[:-1])|(groupowner[1:]!=groupowner[:-1])]);gc=np.diff(np.r_[ga,len(bypart)])
    remainder=[]
    for start,count in zip(ga,gc):
        members=bypart[start:start+count];positive=members[starts[members]<ends[members]];negative=members[starts[members]>ends[members]]
        cancel=min(len(positive),len(negative));remainder.extend(positive[cancel:]);remainder.extend(negative[cancel:])
    remainder=np.asarray(remainder,np.int64);boundary={};neighbors={}
    for edge in remainder:neighbors.setdefault(int(keys[edge]),set()).add(int(own[edge]))
    original_open=0
    for edge in remainder:
        others=neighbors[int(keys[edge])]-{int(own[edge])};other=min(others) if others else 0xffffffff
        original_open+=not bool(others)
        boundary.setdefault(int(own[edge]),[]).append((int(ends[edge]),int(starts[edge]),other))
    cap_vertices=[];cap_indices=[];owner_pairs=[];closed=0;open_edges=0;branched=0
    for part,edges in sorted(boundary.items()):
        outgoing={}
        for j,(a,b,neighbor) in enumerate(edges):outgoing.setdefault(a,[]).append(j)
        branched+=sum(len(v)!=1 for v in outgoing.values());visited=set()
        for first in range(len(edges)):
            if first in visited:continue
            walk=[];j=first;start=edges[first][0]
            while j not in visited:
                visited.add(j);walk.append(j);end=edges[j][1]
                if end==start:break
                candidates=[x for x in outgoing.get(end,[]) if x not in visited]
                if not candidates:break
                j=candidates[0]
            if edges[walk[-1]][1]!=start or len(walk)<3:open_edges+=len(walk);continue
            loop=np.array([points[edges[x][0]] for x in walk]);center=loop.mean(0)
            normal=np.sum(np.cross(loop-center,np.roll(loop,-1,axis=0)-center),axis=0);normal/=max(np.linalg.norm(normal),1e-20)
            tangent=np.cross(normal,[0,1,0] if abs(normal[1])<.9 else [1,0,0]);tangent/=max(np.linalg.norm(tangent),1e-20);bitangent=np.cross(normal,tangent)
            base=len(cap_vertices)
            for p in np.vstack((center,loop)):
                cap_vertices.append([*p,*normal,np.dot(p-center,tangent),np.dot(p-center,bitangent),9])
            for k,edge in enumerate(walk):
                cap_indices.append([base,base+1+k,base+1+(k+1)%len(walk)]);owner_pairs.append([part,edges[edge][2]])
            closed+=1
    return np.asarray(cap_vertices,np.float32).reshape(-1,9),np.asarray(cap_indices,np.uint32).reshape(-1,3),np.asarray(owner_pairs,np.uint32).reshape(-1,2),{'closedLoops':closed,'openInterfaceEdges':open_edges,'originalBoundaryEdges':original_open,'branchedInterfaceVertices':branched,'nonManifoldSourceEdges':int(np.sum(counts>2))}

def partition_caps(vertices,faces,pairs):
    if not len(faces):return vertices,faces,np.empty((0,2),np.uint32)
    keys=np.column_stack((np.repeat(pairs,3,axis=0),faces.reshape(-1)))
    unique,inverse=np.unique(keys,axis=0,return_inverse=True)
    return vertices[unique[:,2]],inverse.astype(np.uint32).reshape(-1,3),unique[:,:2].astype(np.uint32)

def voxel_owners(nodes,parent,radius,size=64):
    z,y,x=np.meshgrid(*([np.arange(size,dtype=np.float32)]*3),indexing='ij')
    points=np.column_stack((x.ravel(),y.ravel(),z.ravel()))*(3/size)+(1.5/size-1.5)
    return closest_beams(points,nodes,parent,radius)

def distribute_proxy_mass(static,owners,solid,density=495):
    """Structural loads use exactly the finite fuel inventory's MODEL mass.

    This deliberately reports the proxy mass separately from analytic rod
    estimates: conservative coarse occupancy is not exact physical mesh volume.
    """
    solid=np.asarray(solid,np.float64).reshape(64,64,64,4);owners=np.asarray(owners,np.uint32).reshape(-1)
    material=solid[...,3];valid=(solid[...,1]>0)&(((material>.5)&(material<2.5)&(solid[...,0]<=0))|((material>7.5)&(solid[...,0]<.07)))
    masses=np.where(valid,solid[...,1]/1.5*density*(3/64)**3,0).reshape(-1)
    analytic=float(static[:,8].sum(dtype=np.float64));n=len(static);own=np.bincount(owners,weights=masses,minlength=n)
    z,y,x=np.mgrid[:64,:64,:64];points=(np.column_stack((x.ravel(),y.ravel(),z.ravel()))+.5)*(3/64)-1.5
    centers=np.column_stack([np.bincount(owners,weights=masses*points[:,j],minlength=n) for j in range(3)])
    mass=own.copy()
    for i in range(n-1,0,-1):p=int(static[i,3]);mass[p]+=mass[i];centers[p]+=centers[i]
    static[:,8]=own;static[:,9]=mass;static[:,12:15]=np.divide(centers,mass[:,None],out=static[:,:3].astype(np.float64).copy(),where=mass[:,None]>0)
    return {'analyticRodMassKg':analytic,'finiteProxyMassKg':float(masses.sum()),'graphOwnMassKg':float(static[:,8].sum(dtype=np.float64)),'massRatio':float(masses.sum()/max(analytic,1e-30)),'method':'Exact same64^3 valid inventory/capacity as wood thermal donors; mass assigned by voxel-owner map','limit':'Coarse conservative collision occupancy is not physical mesh volume; proxy density/fraction needs calibration.'}

def export_graph_mesh(nodes,parent,radius,vertices,faces,triangle_owner=None):
    """Generic authoring entry point for MODEL-metre logs/house/sigil graphs.

    Caller may provide authored triangle ownership. Auto assignment follows the
    same nearest-beam rule as the tree; all input triangles/attributes survive.
    Returns arrays, never writes or simplifies the caller's approved mesh.
    """
    static,bounds,depth=make_graph(np.asarray(nodes,np.float32),np.asarray(parent,np.int32),np.asarray(radius,np.float32))
    owner=closest_beams(vertices[faces,:3].mean(1),nodes,parent,radius) if triangle_owner is None else np.asarray(triangle_owner,np.uint32)
    if len(owner)!=len(faces) or np.any(owner>=len(nodes)):raise ValueError('Invalid triangle ownership')
    pv,pf,po,source=partition_mesh(vertices,faces,owner);cv,cf,cp,report=interior_caps(vertices,faces,owner);cv,cf,cp=partition_caps(cv,cf,cp)
    bounds[:,:3]=np.inf;bounds[:,4:7]=-np.inf
    for axis in range(3):np.minimum.at(bounds[:,axis],po,pv[:,axis]);np.maximum.at(bounds[:,4+axis],po,pv[:,axis])
    for i in range(len(nodes)-1,0,-1):
        p=parent[i];bounds[p,:3]=np.minimum(bounds[p,:3],bounds[i,:3]);bounds[p,4:7]=np.maximum(bounds[p,4:7],bounds[i,4:7])
    empty=~np.isfinite(bounds[:,0]);bounds[empty,:3]=nodes[empty];bounds[empty,4:7]=nodes[empty]
    return {'nodes':static,'bounds':bounds,'vertices':pv,'indices':pf,'owners':np.column_stack((po,np.full(len(po),0xffffffff,np.uint32))),'sourceVertex':source,'capVertices':cv,'capIndices':cf,'capOwners':cp,'maxDepth':depth,'capReport':report}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--asset',type=Path,default=ASSET);parser.add_argument('--skeleton',type=Path);parser.add_argument('--out',type=Path);parser.add_argument('--report',type=Path);args=parser.parse_args()
    manifest=json.loads((args.asset/'manifest.json').read_text());source_hash={}
    for name in ['vertices.bin','indices.bin']:
        source_hash[name]=digest(args.asset/name)
        if source_hash[name]!=manifest['files'][name]['sha256']:raise ValueError('Approved source hash mismatch: '+name)
    vertices=np.fromfile(args.asset/'vertices.bin',dtype='<f4').reshape(-1,9);faces=np.fromfile(args.asset/'indices.bin',dtype='<u4').reshape(-1,3)
    skeleton=args.skeleton or ROOT.parent/f"world/output/forest-refined/assets/{manifest['variant']}-skeleton.npz"
    graph=np.load(skeleton);scale=manifest['normalization']['scale'];center=np.array(manifest['normalization']['center'])
    nodes=((graph['nodes']-center)*scale)[:,[0,2,1]].astype(np.float32);parent=graph['parent'].astype(np.int32);radius=(graph['radius']*scale).astype(np.float32)
    static,bounds,maxdepth=make_graph(nodes,parent,radius)
    wood_count=manifest['sourceMeshes'][0]['triangles'];root_count=manifest['sourceMeshes'][1]['triangles'];source_end=wood_count+root_count
    tri_owner=np.zeros(len(faces),np.uint32);tri_owner[:wood_count]=closest_beams(vertices[faces[:wood_count],:3].mean(1),nodes,parent,radius)
    tri_owner[source_end:],components=component_owners(vertices,faces[source_end:],nodes,parent,radius)
    pv,pf,po,source_vertex=partition_mesh(vertices,faces,tri_owner)
    cv,cf,cp,cap_report=interior_caps(vertices,faces[:wood_count],tri_owner[:wood_count]);cv,cf,cp=partition_caps(cv,cf,cp)
    # Exact full-tuple equality gate, including every rest triangle and UV seam.
    if not np.array_equal(pv[pf],vertices[faces]):raise ValueError('Partition changed source attributes')
    bounds[:,:3]=np.inf;bounds[:,4:7]=-np.inf
    for axis in range(3):np.minimum.at(bounds[:,axis],po,pv[:,axis]);np.maximum.at(bounds[:,4+axis],po,pv[:,axis])
    for i in range(len(nodes)-1,0,-1):
        p=parent[i];bounds[p,:3]=np.minimum(bounds[p,:3],bounds[i,:3]);bounds[p,4:7]=np.maximum(bounds[p,4:7],bounds[i,4:7])
    empty=~np.isfinite(bounds[:,0]);bounds[empty,:3]=nodes[empty];bounds[empty,4:7]=nodes[empty]
    voxel=voxel_owners(nodes,parent,radius)
    report={'layoutVersion':1,'sourceHashes':source_hash,'skeletonHash':digest(skeleton),'nodes':len(nodes),'maxDepth':maxdepth,'sourceVertices':len(vertices),'sourceTriangles':len(faces),'partitionVertices':len(pv),'duplicatedVertices':len(pv)-len(vertices),'partitionTriangles':len(pf),'foliageComponents':components,'caps':{'vertices':len(cv),'triangles':len(cf),**cap_report},'exactRestAttributes':True,'geometrySimplified':False,'bytes':{'static':static.nbytes,'bounds':bounds.nbytes,'vertices':pv.nbytes,'indices':pf.nbytes,'owners':len(po)*8,'sourceVertex':source_vertex.nbytes,'capVertices':cv.nbytes,'capIndices':cf.nbytes,'capOwnerPairs':cp.nbytes,'voxelOwners':voxel.nbytes},'physicalUnits':'MODEL metres, kg and Pa; runtime objectScale scales mass by s^3','layout':{'node':'restParent vec4, axisRadius vec4, ownMass/subtreeMass/length/anchor vec4, subtreeCOM/strengthPa vec4','owner':'uint32 owner, uint32 otherCapOwner; 0xffffffff means ordinary surface or original boundary cap','capOwnerPairs':'PER VERTEX uint32 pair','voxelOwners':'64^3 uint32, x fastest, rest coordinates [-1.5,1.5] cell centres'},'limits':['Nearest-beam partition is reduced authored fracture geometry, not crack propagation.','Cap fans follow exact interface loops; nonplanar interfaces use planar interpolated interior normals.','Five-point beam sampling and strength loss are reduced mechanics.']}
    report['totalAssetBytes']=sum(report['bytes'].values())
    if report['totalAssetBytes']>100*1024*1024:raise ValueError('Partition exceeds 100 MiB asset budget; report before shipping')
    if args.out:
        args.out.mkdir(parents=True,exist_ok=True)
        arrays={'nodes.bin':static,'bounds.bin':bounds,'vertices.bin':pv,'indices.bin':pf,'owners.bin':np.column_stack((po,np.full(len(po),0xffffffff,np.uint32))),'source-vertex.bin':source_vertex,'cap-vertices.bin':cv,'cap-indices.bin':cf,'cap-owner-pairs.bin':cp,'voxel-owners.bin':voxel}
        for name,array in arrays.items():array.astype(array.dtype.newbyteorder('<')).tofile(args.out/name)
        report['files']={name:{'bytes':(args.out/name).stat().st_size,'sha256':digest(args.out/name)} for name in arrays}
        (args.out/'manifest.json').write_text(json.dumps(report,indent=2))
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ['nodes','maxDepth','sourceVertices','partitionVertices','duplicatedVertices','sourceTriangles','caps','totalAssetBytes','exactRestAttributes']}))

if __name__=='__main__':main()
