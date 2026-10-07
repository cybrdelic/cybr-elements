"""Static wood geometry companions for existing logs/house and native CYBR mark.

No fire frames. Existing signed-distance proxies remain untouched. The sigil's
native R support channel (NOT alpha: alpha is launch direction) is extruded with
all native contour samples and holes. Structural graphs are reduced authored
beam supports; they do not model redundant timber joints or engineering fracture.
"""
from pathlib import Path
import json,hashlib,argparse
import numpy as np
from scipy.ndimage import distance_transform_edt,map_coordinates,zoom,label
from skimage.measure import find_contours,marching_cubes
from skimage.morphology import skeletonize
import shapely
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from export_wood_structure import export_graph_mesh,voxel_owners,digest,closest_beams

ROOT=Path(__file__).resolve().parents[2]
LIVE=ROOT/'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'
OBJECTS=LIVE/'pyro-gpu/objects'

def beam_graph(segments,spacing=.16):
    nodes=[[0,-1.35,0]];parents=[-1];radii=[.02];anchors=[0]
    for a,b,r in segments:
        a=np.asarray(a,float);b=np.asarray(b,float);steps=max(2,int(np.ceil(np.linalg.norm(b-a)/spacing)))
        first=len(nodes);nodes.append(a.tolist());parents.append(0);radii.append(r);anchors.append(first)
        for j in range(1,steps+1):nodes.append((a+(b-a)*j/steps).tolist());parents.append(len(nodes)-2);radii.append(r)
    return np.asarray(nodes,np.float32),np.asarray(parents,np.int32),np.asarray(radii,np.float32),anchors

def logs_graph():
    segments=[([-.80,-.47,z],[.80,-.47,z],.15) for z in [-.43,0,.43]]
    segments +=[([x,-.19,-.67],[x,-.19,.67],.14) for x in [-.45,.45]]
    segments +=[([-.60,.07,-.08],[.65,.07,.16],.13)]
    return beam_graph(segments)

def house_graph():
    # Actual wall/post/roof spans from tools/fire-sources/build.py, with several
    # finite beam sections per span. Multiple grounded posts remain anchored.
    nodes=[[0,-1.35,0]];parents=[-1];radii=[.02];anchors=[0];virtual=[0]
    def append(a,b,r,ground=False):
        a=np.asarray(a,float);b=np.asarray(b,float);distance=np.linalg.norm(np.asarray(nodes)-a,axis=1);start=int(np.argmin(distance))
        if distance[start]>1e-6:
            previous=0 if ground else start;start=len(nodes);nodes.append(a.tolist());parents.append(previous);radii.append(r);virtual.append(start)
            if ground:anchors.append(start)
        steps=max(2,int(np.ceil(np.linalg.norm(b-a)/.22)));previous=start
        for j in range(1,steps+1):
            node=len(nodes);nodes.append((a+(b-a)*j/steps).tolist());parents.append(previous);radii.append(r);previous=node
    for x in [-1.03,1.03]:
        for z in [-.71,.71]:append([x,-1.25,z],[x,.15,z],.055,True)
    for z in [-.74,.74]:
        for y in [-1.1,-.7,-.25,.02]:append([-1.08,y,z],[1.08,y,z],.065)
    for x in [-1.06,1.06]:
        for y in [-1.1,-.7,-.25,.02]:append([x,y,-.76],[x,y,.76],.065)
    for z in [-.8,-.4,0,.4,.8]:
        append([-1.2,.004,z],[0,.58,z],.065);append([1.2,.004,z],[0,.58,z],.065)
    return np.asarray(nodes,np.float32),np.asarray(parents,np.int32),np.asarray(radii,np.float32),anchors,virtual

def surface_from_proxy(name):
    path=OBJECTS/f'{name}.rgba16.bin';raw=np.fromfile(path,dtype='<f2').astype(np.float32).reshape(64,64,64,4)
    # Cubic interpolation smooths the existing sampled SDF; no geometry source
    # proxy is rewritten and no newly invented windows/roof spans are added.
    sdf=zoom(raw[...,0],3,order=1,grid_mode=False);size=len(sdf)
    points,faces,normals,_=marching_cubes(sdf,0,spacing=(3/64*63/(size-1),)*3,gradient_direction='ascent')
    points=points[:,[2,1,0]]-1.5+1.5/64;normals=normals[:,[2,1,0]];faces=faces[:,[0,2,1]]
    coords=((points+1.5)/(3/64)-.5)[:,[2,1,0]].T
    mat=map_coordinates(raw[...,3],coords,order=0,mode='nearest')
    uv=points[:,[0,1]];vertices=np.column_stack((points,normals,uv,mat)).astype(np.float32)
    return vertices,faces.astype(np.uint32),{'sourceProxy':str(path.relative_to(ROOT)).replace('\\','/'),'sourceProxySha256':digest(path),'method':'Isosurface of unchanged64^3 signed-distance proxy, linearly resampled192^3','proxyRewritten':False}

def sigil_geometry():
    source=LIVE/'source/source-native.rgba8.bin';field=np.fromfile(source,dtype=np.uint8).reshape(504,896,4)[...,0]/255
    mask=field>=.5;contours=find_contours(field,.5,fully_connected='high');rings=[]
    for c in contours:
        xy=np.column_stack(((c[:,1]+.5)*3.5/896-1.75,(c[:,0]+.5)*1.96875/504-.7375))
        if np.linalg.norm(xy[0]-xy[-1])>1e-8:raise ValueError('Native support must have zero border and closed rings')
        rings.append(Polygon(xy))
    parents=[]
    for i,p in enumerate(rings):
        containing=[j for j,q in enumerate(rings) if j!=i and q.area>p.area and q.contains(p.representative_point())]
        parents.append(min(containing,key=lambda j:rings[j].area) if containing else -1)
    depth=[]
    for i in range(len(rings)):
        p=parents[i];d=0
        while p>=0:d+=1;p=parents[p]
        depth.append(d)
    polygons=[orient(Polygon(rings[i].exterior.coords,[rings[j].exterior.coords for j in range(len(rings)) if parents[j]==i and depth[j]%2]),1) for i in range(len(rings)) if depth[i]%2==0]
    x,y=np.meshgrid((np.arange(896)+.5)*3.5/896-1.75,(np.arange(504)+.5)*1.96875/504-.7375)
    predicted=np.zeros(mask.shape,bool)
    for p in polygons:predicted|=shapely.contains_xy(p,x,y)
    if not np.array_equal(predicted,mask):raise ValueError('Sigil contour changed native pixel support')
    verts=[];faces=[]
    def triangle(points,normal):
        start=len(verts)
        for p in points:verts.append([*p,*normal,p[0],p[1],1])
        faces.append([start,start+1,start+2])
    for poly in polygons:
        for tri in shapely.constrained_delaunay_triangles(poly).geoms:
            q=np.asarray(orient(tri,1).exterior.coords)[:3]
            triangle([[a,b,.018] for a,b in q],[0,0,1]);triangle([[a,b,-.018] for a,b in q[::-1]],[0,0,-1])
        for ring in [poly.exterior,*poly.interiors]:
            q=np.asarray(ring.coords)
            for a,b in zip(q[:-1],q[1:]):
                d=b-a;n=np.array([d[1],-d[0],0]);n/=max(np.linalg.norm(n),1e-20)
                triangle([[*a,-.018],[*b,-.018],[*b,.018]],n);triangle([[*a,-.018],[*b,.018],[*a,.018]],n)
    vertices,inverse=np.unique(np.asarray(verts,np.float32),axis=0,return_inverse=True);faces=inverse.reshape(-1,3).astype(np.uint32)
    provenance={'sourceSupport':str(source.relative_to(ROOT)).replace('\\','/'),'sourceSupportSha256':digest(source),'supportChannel':'R; alpha is launchDirectionZ','nativeSupportPixels':int(mask.sum()),'nativePixelMaskExact':True,'components':len(polygons),'holes':sum(len(p.interiors) for p in polygons),'method':'Native bilinear edge intersections with piecewise linear contours; every native contour sample retained','thicknessMetres':.036,'limits':['Polyline interpolation approximates bilinear contour curvature between native edge intersections.']}
    return vertices,faces,mask,provenance,polygons

def sigil_graph(mask):
    sk=skeletonize(mask);components,count=label(sk,structure=np.ones((3,3)))
    width=distance_transform_edt(mask)*3.5/896
    nodes=[[0,-.75,0]];parents=[-1];radii=[.02];anchors=[0]
    # Breadth-first pixel traversal gives a deterministic spanning tree. Keep
    # junctions, tips and every twelfth pixel along an unbranched run.
    for component in range(1,count+1):
        pixels=np.argwhere(components==component);pixelset={tuple(p) for p in pixels};start=tuple(pixels[np.argmin(pixels[:,0])])
        adjacency={p:[(p[0]+dy,p[1]+dx) for dy in [-1,0,1] for dx in [-1,0,1] if (dy or dx) and (p[0]+dy,p[1]+dx) in pixelset] for p in pixelset}
        queue=[start];seen={start};nearest={start:len(nodes)};distance={start:0};nodes.append([(start[1]+.5)*3.5/896-1.75,(start[0]+.5)*1.96875/504-.7375,0]);parents.append(0);radii.append(float(np.sqrt(max(width[start],.003)*.018)));anchors.append(len(nodes)-1)
        for p in queue:
            children=[q for q in adjacency[p] if q not in seen]
            for q in children:
                seen.add(q);queue.append(q);d=distance[p]+1;previous=nearest[p]
                if d>=12 or len(adjacency[q])!=2:
                    nearest[q]=len(nodes);distance[q]=0;nodes.append([(q[1]+.5)*3.5/896-1.75,(q[0]+.5)*1.96875/504-.7375,0]);parents.append(previous);radii.append(float(np.sqrt(max(width[q],.003)*.018)))
                else:nearest[q]=previous;distance[q]=d
    return np.asarray(nodes,np.float32),np.asarray(parents,np.int32),np.asarray(radii,np.float32),anchors

def sigil_proxy(mask,polygons):
    h=3.5/896;signed=(distance_transform_edt(~mask)-distance_transform_edt(mask))*h
    z,y,x=np.mgrid[:64,:64,:64];px=(x+.5)*3/64-1.5;py=(y+.5)*3/64-1.5;pz=(z+.5)*3/64-1.5
    coords=np.array([(py+.7375)/1.96875*504-.5,(px+1.75)/3.5*896-.5]);distance=map_coordinates(signed,coords,order=1,mode='constant',cval=3)
    d=np.maximum(distance,np.abs(pz)-.018);cell=3/64
    xx,yy=np.meshgrid((np.arange(64)+.5)*cell-1.5,(np.arange(64)+.5)*cell-1.5)
    artwork=shapely.union_all(polygons);boxes=shapely.box(xx-cell*.5,yy-cell*.5,xx+cell*.5,yy+cell*.5)
    area=shapely.area(shapely.intersection(boxes,artwork))/(cell*cell)
    zz=(np.arange(64)+.5)*cell-1.5;depth=np.maximum(np.minimum(zz+cell*.5,.018)-np.maximum(zz-cell*.5,-.018),0)/cell
    fraction=depth[:,None,None]*area[None,:,:]
    # Conservative collision proxy, EXACT polygon/voxel volume inventory.
    # Geometry remains .036m thick; a centre-sampled SDF otherwise misses it.
    d=np.where(fraction>0,-np.minimum(fraction*cell,cell*.5),d)
    out=np.stack((d,1.5*fraction,np.ones_like(d),np.ones_like(d)),axis=-1)
    return out.astype('<f2')

def write(name,vertices,faces,graph,provenance,solid=None):
    nodes,parent,radius,anchors=graph[:4];virtual=graph[4] if len(graph)>4 else anchors;physical_parent=parent.copy();physical_parent[virtual]=-1
    owners=closest_beams(vertices[faces,:3].mean(1),nodes,physical_parent,radius)
    inert=np.all(vertices[faces,8]>2.5,axis=1)&np.all(vertices[faces,8]<7.5,axis=1);owners[inert]=0
    arrays=export_graph_mesh(nodes,parent,radius,vertices,faces,owners)
    arrays['nodes'][anchors,11]=1;arrays['nodes'][virtual,8]=0
    # Virtual support links contain no wood and add no mass or heat samples.
    own=arrays['nodes'][:,8].astype(np.float64);mass=own.copy();centroid=np.zeros((len(nodes),3),float)
    for i in range(1,len(nodes)):centroid[i]=(nodes[i]+nodes[parent[i]])*.5*own[i]
    for i in range(len(nodes)-1,0,-1):mass[parent[i]]+=mass[i];centroid[parent[i]]+=centroid[i]
    arrays['nodes'][:,9]=mass;arrays['nodes'][:,12:15]=np.divide(centroid,mass[:,None],out=nodes.astype(float).copy(),where=mass[:,None]>0)
    arrays['voxelOwners']=voxel_owners(nodes,physical_parent,radius)
    mapping={'nodes':'nodes.bin','bounds':'bounds.bin','vertices':'vertices.bin','indices':'indices.bin','owners':'owners.bin','sourceVertex':'source-vertex.bin','capVertices':'cap-vertices.bin','capIndices':'cap-indices.bin','capOwners':'cap-owner-pairs.bin','voxelOwners':'voxel-owners.bin'}
    target=OBJECTS/name;target.mkdir(exist_ok=True)
    for key,file in mapping.items():arrays[key].astype(arrays[key].dtype.newbyteorder('<')).tofile(target/file)
    if solid is not None:solid.tofile(target/'solid.rgba16.bin')
    manifest={'layoutVersion':1,'id':name,'nodes':len(nodes),'maxDepth':arrays['maxDepth'],'vertexStride':36,'partitionVertices':len(arrays['vertices']),'partitionTriangles':len(faces),'caps':{'vertices':len(arrays['capVertices']),'triangles':len(arrays['capIndices']),**arrays['capReport']},'materialIds':{'wood':1,'roofWood':2,'inertChimney':3,'freshInteriorCap':9},'ownerLayout':'pervertex uint32 owner,uint32other;other=0xffffffff ordinary/originalboundarycap','nodeLayout':'restParent/axisRadius/ownMass-subtreeMass-length-anchor/subtreeCOM-strengthPa,64B MODELmetres/kg/Pa','provenance':provenance,'files':{file:{'bytes':(target/file).stat().st_size,'sha256':digest(target/file)} for file in [*mapping.values(),*(['solid.rgba16.bin'] if solid is not None else [])]},'limits':['Authored tree of supports omits redundant joints and elastic bending before fracture.','Rigid beam fragments and cap fans are a reduced approximation.']}
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2));return {'id':name,'nodes':len(nodes),'depth':arrays['maxDepth'],'vertices':len(arrays['vertices']),'triangles':len(faces),'capTriangles':len(arrays['capIndices']),'openCapEdges':arrays['capReport']['openInterfaceEdges'],'bytes':sum(p.stat().st_size for p in target.iterdir())}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--only',choices=['all','sigil','logs','house'],default='all');args=parser.parse_args();summary=[]
    for name,maker in [('logs',logs_graph),('house',house_graph)]:
        if args.only not in ['all',name]:continue
        v,f,p=surface_from_proxy(name);summary.append(write(name,v,f,maker(),p))
    if args.only in ['all','sigil']:
        v,f,mask,p,polygons=sigil_geometry();proxy=sigil_proxy(mask,polygons)
        expected=float(sum(q.area for q in polygons)*.036);measured=float(proxy[...,1].astype(np.float64).sum()/1.5*(3/64)**3)
        p['proxyInventory']={'method':'Exact contour polygon/voxel intersection; conservative collision cells carry fractional wood volume','geometryVolumeM3':expected,'halfFloatInventoryVolumeM3':measured,'relativeQuantizationError':abs(measured-expected)/expected,'occupiedCells':int(np.count_nonzero(proxy[...,1]>0))}
        summary.append(write('wood-sigil',v,f,sigil_graph(mask),p,proxy))
    report=ROOT/'work/wood-structure-qa/preset-export.json';report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(summary,indent=2));print(json.dumps(summary))

if __name__=='__main__':main()
