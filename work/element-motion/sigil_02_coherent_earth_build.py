"""Interlocking 3D fracture pieces cut from the approved full 02 silhouette."""
from pathlib import Path
import json,numpy as np,cv2,shapely
from shapely.geometry import Polygon,MultiPoint,box
from scipy.ndimage import map_coordinates
R=Path(__file__).resolve().parent;O=R/'sigil-02-coherent';O.mkdir(exist_ok=True)
s=np.load(R/'sigil-02-v2/source.npz');lo=s['lo'];ext=s['extent'];h,w=s['sdf'].shape
mask=(s['sdf']>0).astype(np.uint8);contours,hierarchy=cv2.findContours(mask,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
def world(c):
 p=c[:,0].astype(float);return np.column_stack((lo[0]+p[:,0]/(w-1)*ext[0],lo[2]+p[:,1]/(h-1)*ext[2]))
polys=[]
for i,c in enumerate(contours):
 if hierarchy[0,i,3]>=0 or len(c)<3:continue
 holes=[world(contours[j]) for j in range(len(contours)) if hierarchy[0,j,3]==i and len(contours[j])>=3]
 p=Polygon(world(c),holes).buffer(0).simplify(.008,preserve_topology=True)
 if p.area>.004:polys.append(p)
glyph=shapely.union_all(polys);rng=np.random.default_rng(8127)
xx,zz=np.meshgrid(np.arange(-4.2,4.3,.34),np.arange(.25,3.7,.32));points=np.column_stack((xx.ravel(),zz.ravel()))+rng.normal(0,.075,(xx.size,2))
regions=shapely.voronoi_polygons(MultiPoint(points),extend_to=box(-5,-1,5,5))
def sample(name,x,z):return float(map_coordinates(s[name],[[(z-lo[2])/ext[2]*(h-1)],[(x-lo[0])/ext[0]*(w-1)]],order=1)[0])
pieces=[]
for cell in regions.geoms:
 cut=cell.intersection(glyph)
 for p in (list(cut.geoms) if hasattr(cut,'geoms') else [cut]):
  if p.geom_type!='Polygon' or p.area<.0006:continue
  p=p.buffer(-.0022,join_style=2)
  if p.is_empty or p.geom_type!='Polygon':continue
  p=shapely.segmentize(p,.075);triangles=shapely.constrained_delaunay_triangles(p)
  coords=[];lookup={};faces=[]
  def vertex(x,z):
   key=(round(x,7),round(z,7))
   if key not in lookup:lookup[key]=len(coords);coords.append([x,z])
   return lookup[key]
  for t in triangles.geoms:
   v=list(t.exterior.coords)[:3];faces.append([vertex(x,z) for x,z in v])
  boundary=[]
  for ring in [p.exterior,*p.interiors]:
   q=list(ring.coords);boundary.extend([(vertex(*a),vertex(*b)) for a,b in zip(q[:-1],q[1:])])
  uv=np.array(coords);n=len(uv);x,z=uv.T
  # Continuous geological relief across fractures, varied edge thickness.
  relief=.022*np.sin(x*15+z*9)+.010*np.sin(x*41-z*23)+.006*np.sin(x*89+z*63)
  middle=.035*np.sin(x*2+z);thickness=.20+.025*np.sin(x*4-z*2)
  front=np.column_stack((x,middle-thickness*.5+relief,z));back=np.column_stack((x,middle+thickness*.5+relief*.3,z))
  verts=np.concatenate((front,back));fs=[f[::-1] for f in faces]+[[i+n for i in f] for f in faces]
  fs.extend([[a,b,b+n,a+n] for a,b in boundary]);center=verts.mean(0)
  birth=.28+(sample('arrival',*p.representative_point().coords[0])-.30)/3.60*1.55
  pieces.append(dict(verts=np.round(verts-center,6).tolist(),faces=fs,frontFaces=len(faces),center=center.tolist(),birth=birth,area=p.area,volume=p.area*float(thickness.mean()),seed=len(pieces)))
(O/'earth-geometry.json').write_text(json.dumps(dict(pieces=pieces,area=glyph.area,source='Approved02 source.npz silhouette',gap=.0044)))
print(json.dumps(dict(pieces=len(pieces),area=glyph.area,vertices=sum(len(p['verts']) for p in pieces),output=str(O/'earth-geometry.json'))))
