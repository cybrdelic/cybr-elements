"""Original-vector repair geometry; CPU construction without Blender."""
from pathlib import Path
import re,xml.etree.ElementTree as ET,json,numpy as np
from shapely.geometry import Polygon,box
from shapely.ops import unary_union,triangulate
R=Path(__file__).resolve().parent
src=R.parents[2]/'outputs/cybrdelic-type/typefaces/vector/CybrdelicSigil-Regular-wordmark.svg'
polys=[]
for node in ET.parse(src).getroot().iter():
 if node.tag.endswith('path'):
  for co in re.split('[Mm]',node.attrib['d'])[1:]:
   p=np.array(list(map(float,re.findall(r'-?\d+(?:\.\d+)?',co)))).reshape(-1,2)
   if len(p)>2:polys.append(p)
allp=np.concatenate(polys);lo=allp.min(0);span=np.ptp(allp,axis=0);positive=[];negative=[]
for p in polys:
 area=np.sum(p[:,0]*np.roll(p[:,1],-1)-p[:,1]*np.roll(p[:,0],-1));q=(p-lo)/span[0]*4.5;q[:,0]-=1.8;q[:,1]=1.9+(span[1]/span[0]*4.5)/2-q[:,1]
 (positive if area>0 else negative).append(Polygon(q).buffer(0))
identity=unary_union(positive).difference(unary_union(negative));out=R/'cpu/identity';out.mkdir(parents=True,exist_ok=True)
from shapely import contains_xy
rng=np.random.default_rng(141);bounds=identity.bounds;candidates=rng.uniform([bounds[0],bounds[1]],[bounds[2],bounds[3]],(500000,2));inside=contains_xy(identity,candidates[:,0],candidates[:,1]);points=candidates[inside][:110000];base=np.c_[(points[:,0]-.45)*2.75/4.5,rng.normal(0,.003,len(points)),(points[:,1]-1.9)*2.75/4.5]
np.savez_compressed(out/'projection.npz',base=base.astype('f4'))

def extrude(g,thickness=.045):
 vertices=[];faces=[]
 for poly in getattr(g,'geoms',[g]):
  if poly.is_empty or poly.geom_type!='Polygon':continue
  mapping={}
  def idx(x,z,side):
   key=(round(x,9),round(z,9),side)
   if key not in mapping:mapping[key]=len(vertices);vertices.append([x,thickness*side/2,z])
   return mapping[key]
  for tri in triangulate(poly):
   if not poly.covers(tri):continue
   points=list(tri.exterior.coords)[:3]
   for side in [-1,1]:
    ids=[idx(x,z,side) for x,z in points];faces.append(ids if side==-1 else ids[::-1])
  for ring in [poly.exterior,*poly.interiors]:
   pts=list(ring.coords)
   for (x,z),(xx,zz) in zip(pts[:-1],pts[1:]):
    a,b,c,d=idx(x,z,-1),idx(xx,zz,-1),idx(xx,zz,1),idx(x,z,1);faces.extend([[a,c,b],[a,d,c]])
 return np.asarray(vertices,dtype='f4').reshape(-1,3),np.asarray(faces,dtype='i4').reshape(-1,3)
records=[]
for f in [15,30,45,52,65,85]:
 t=(f+1)/30;progress=np.clip((t-.50)/1.6,0,1);front=-1.8+progress*4.5;cuts=[]
 for i,x in enumerate(np.linspace(-1.55,2.4,9)):
  width=.043*(1-np.clip((front-x+.05)/.23,0,1))
  if width>.0001:cuts.append(Polygon([(x-width,1.0),(x+width,1.0),(x+.22+width,2.8),(x+.22-width,2.8)]))
 removed=unary_union(cuts);body=identity.difference(removed);active=identity.intersection(box(front-.04,.8,front+.04,3));v,fa=extrude(body);fv,ff=extrude(active,.046)
 np.savez_compressed(out/f'healing-{f:04}.npz',v=v,f=fa,front_v=fv,front_f=ff,progress=progress)
 records.append({'frame':f,'progress':float(progress),'missingArea':float(identity.area-body.area),'originalArea':float(identity.area),'vertices':len(v)})
assert all(a['missingArea']>=b['missingArea']-1e-8 for a,b in zip(records,records[1:]));assert records[-1]['missingArea']<1e-8
(out/'repair.json').write_text(json.dumps({'source':str(src),'mechanism':'Actual geometric gaps close behind the traveling treatment front','frames':records},indent=2));print('CPU identity repair:',len(records),'frames; final gap area',records[-1]['missingArea'])
