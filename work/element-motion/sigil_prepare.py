"""Use the approved study-06 artwork, retaining its counters and l/i gap."""
from pathlib import Path
import json, hashlib
import numpy as np, cv2
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt, gaussian_filter

R=Path(__file__).resolve().parent; B=R/'sigil-v1'; B.mkdir(exist_ok=True)
SOURCE=R.parents[1]/'outputs/cybrdelic-type/exploration-v6/cybrdelic-brandmark-refined.png'
art=np.array(Image.open(SOURCE).convert('L'))
W,H=1024,576; WX=11.4; WZ=WX*9/16; CENTER=2.95
xx,zz=np.meshgrid(np.linspace(-WX/2,WX/2,W),np.linspace(CENTER-WZ/2,CENTER+WZ/2,H))
sheet=Image.new('RGB',(1440,810)); draw=ImageDraw.Draw(sheet)
for row,variant in enumerate(['01','02']):
    top,bottom=(95,535) if variant=='01' else (585,1005)
    mask=(art[top:bottom,20:1005]<100).astype('uint8')
    n,labels,stats,centers=cv2.connectedComponentsWithStats(mask)
    for k in range(1,n):
        if stats[k,4]<35 or (centers[k,0]<85 and centers[k,1]<130):mask[labels==k]=0
    ys,xs=np.where(mask); mask=mask[ys.min():ys.max()+1,xs.min():xs.max()+1]
    scale=8.6/mask.shape[1];oldscale=8.05/mask.shape[1];oldcenter=.43+mask.shape[0]*oldscale/2
    sx=(xx/scale+mask.shape[1]/2).astype('f');sy=(mask.shape[0]/2-(zz-CENTER)/scale).astype('f')
    sd=(distance_transform_edt(mask)-distance_transform_edt(1-mask))*scale
    sd=gaussian_filter(sd,.55).astype('f')
    sdf=cv2.remap(sd,sx,sy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=-1).astype('f')
    m=sdf>0
    old=np.load(R.parent/f'brand-fire-{variant}.npz'); support=old['supply']
    nearest=distance_transform_edt(1-support,return_distances=False,return_indices=True)
    oldarrival=old['arrival'][tuple(nearest)].astype('f')
    oldx=xx*8.05/8.6;oldz=(zz-CENTER)*8.05/8.6+oldcenter
    arrival=cv2.remap(oldarrival,((oldx+5.25)/10.5*511).astype('f'),(oldz/5.8*319).astype('f'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
    arrival=(.3+np.clip((arrival-.08)/old['times'][-1],0,1)*2.9).astype('f')
    points=old['points'].copy();points[:,0]*=8.6/8.05;points[:,1]=CENTER+(points[:,1]-oldcenter)*8.6/8.05
    times=.3+old['times']/old['times'][-1]*2.9
    gz,gx=np.gradient(sdf,WZ/(H-1),WX/(W-1))
    np.savez_compressed(B/f'mark-{variant}.npz',mask=m,sdf=sdf,arrival=arrival,points=points,times=times,emit=old['emit'],gx=gx,gz=gz)
    # Node reads bounded binary fields without adding an image library.
    fields=np.stack([sdf,arrival,gx,gz],axis=0).astype('<f4');(B/f'mark-{variant}.bin').write_bytes(fields.tobytes())
    im=Image.fromarray(np.flipud(np.uint8(m)*255));im.resize((1440,810)).save(B/f'mark-{variant}-readability.png')
    small=im.resize((1440,810));sheet.paste(small.resize((1440,405)),(0,row*405));draw.text((20,row*405+20),variant,fill='#a0a0a0')
    meta=dict(variant=variant,source=str(SOURCE),sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),fieldSize=[W,H],worldWidth=WX,worldHeight=WZ,centerZ=CENTER,markWidth=8.6,start=.3,writeEnd=3.2,release=6.2,duration=10,fps=30,pixelCoverage=float(m.mean()),preserved='Exact established silhouette; no font substitution, white text or opaque outline')
    (B/f'mark-{variant}.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(variant,'field',m.shape,'mask pixels',int(m.sum()),'writing',round(times[-1],2),flush=True)
sheet.save(B/'marks-readability.jpg',quality=94)
