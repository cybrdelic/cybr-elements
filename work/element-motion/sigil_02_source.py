"""Build a volumetric emitter cross-section from the approved 02 artwork.

The silhouette describes newly supplied fuel, never a mask on the simulation
or on the rendered image. No skeleton controls its width or topology.
"""
from pathlib import Path
import hashlib,json,sys
import numpy as np,cv2
from scipy.ndimage import distance_transform_edt,gaussian_filter
from skimage.graph import MCP_Geometric
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;edition=sys.argv[1] if len(sys.argv)>1 else 'sigil-02';assert edition in ['sigil-02','sigil-02-v2'];O=R/edition;O.mkdir(exist_ok=True)
source=R.parents[1]/'outputs/cybrdelic-type/exploration-v6/cybrdelic-brandmark-refined.png'
art=np.array(Image.open(source).convert('L'));crop=art[585:1005,20:1005]
mask=(crop<100).astype('uint8');n,labels,stats,centroids=cv2.connectedComponentsWithStats(mask)
for k in range(1,n):
 if stats[k,4]<35 or (centroids[k,0]<85 and centroids[k,1]<130):mask[labels==k]=0
yy,xx=np.where(mask);mask=mask[yy.min():yy.max()+1,xx.min():xx.max()+1]
height,width=mask.shape;scale=8.0/width;center=1.95
sdf=(distance_transform_edt(mask)-distance_transform_edt(1-mask))*scale
n,labels,stats,centroids=cv2.connectedComponentsWithStats(mask)
arrival=np.full(mask.shape,np.nan,np.float64)
for k in range(1,n):
 region=labels==k;ys,xs=np.where(region);left=xs.min();candidates=np.argwhere(region&(np.indices(mask.shape)[1]<=left+12))
 root=max(candidates,key=lambda q:sdf[tuple(q)])
 distance,_=MCP_Geometric(np.where(region,1.,np.inf)).find_costs([tuple(root)])
 arrival[region]=(root[1]*scale/2.4)+distance[region]*scale/3.2
arrival[mask>0]=.30+(arrival[mask>0]-np.nanmin(arrival))/(np.nanmax(arrival)-np.nanmin(arrival))*3.60
near=distance_transform_edt(1-mask,return_distances=False,return_indices=True)
arrival=np.where(mask,arrival,arrival[tuple(near)])
smooth=gaussian_filter(arrival,1.2);gy,gx=np.gradient(smooth,scale);gz=-gy;length=np.hypot(gx,gz);gx/=np.maximum(length,1e-8);gz/=np.maximum(length,1e-8)
X,Z=(896,504) if edition.endswith('v2') else (768,432);lo=np.array([-7.,-.6,-1.05]) if edition.endswith('v2') else np.array([-5.25,-.6,-1.05]);extent=np.array([14.,1.2,7.875]) if edition.endswith('v2') else np.array([10.5,1.2,5.90625])
worldx,worldz=np.meshgrid(np.linspace(lo[0],lo[0]+extent[0],X),np.linspace(lo[2],lo[2]+extent[2],Z))
px=(worldx/scale+(width-1)/2).astype('f');py=((height-1)/2-(worldz-center)/scale).astype('f')
def sample(field,border=0):return cv2.remap(field.astype('f'),px,py,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=border)
distance=sample(sdf,-1);dx=extent[0]/(X-1);support=np.clip(distance/dx+.5,0,1).astype('f');reference=cv2.remap(mask,px,py,cv2.INTER_NEAREST)>0;actual=support>.5
intersection=np.count_nonzero(reference&actual);union=np.count_nonzero(reference|actual);iou=intersection/union
def topology(binary):
 binary=binary.astype('uint8').copy();count,lab,stats,_=cv2.connectedComponentsWithStats(binary)
 # Ignore sub-pixel tip islands in this topology check; leave the source intact.
 for i in range(1,count):
  if stats[i,4]<4:binary[lab==i]=0
 c,h=cv2.findContours(binary,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
 return {'components':int(np.sum(h[0,:,3]<0)),'holes':int(np.sum(h[0,:,3]>=0))}
top=topology(actual);original_top=topology(mask);assert iou>.990,(iou,top);assert top==original_top,(top,original_top)
np.savez_compressed(O/'source.npz',support=support,sdf=distance,arrival=sample(arrival,999),dirx=sample(gx),dirz=sample(gz),lo=lo,extent=extent)
sheet=Image.new('RGB',(1280,1120),(12,12,12));draw=ImageDraw.Draw(sheet)
for row,(name,m) in enumerate([('APPROVED 02 / artwork',mask),('FUEL SOURCE / full stroke widths and cutouts',np.flipud(actual.astype('uint8')))]):
 ys,xs=np.where(m);m=m[ys.min():ys.max()+1,xs.min():xs.max()+1];im=Image.fromarray(np.uint8(m)*255).convert('RGB');factor=min(1220/im.width,495/im.height);im=im.resize((round(im.width*factor),round(im.height*factor)),Image.Resampling.LANCZOS);x=(1280-im.width)//2;y=row*560+44+(495-im.height)//2;sheet.paste(im,(x,y));draw.text((30,row*560+16),name,fill=(185,185,185))
sheet.save(O/'source-review.jpg',quality=94)
report={'source':str(source),'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'variant':'02','method':'Full tapered artwork cross-section, extruded into a corrugated fuel sheet; geodesic ignition order','sourceGrid':[X,Z],'worldWidth':8.0,'centerZ':center,'sourceIntersectionOverUnion':iou,'artworkTopology':original_top,'sourceTopology':top,'start':.30,'writeEnd':3.90,'supplyEnd':6.8,'duration':9.8,'sourceOnly':True,'noRenderMask':True,'noCombustionMask':True}
(O/'source-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
