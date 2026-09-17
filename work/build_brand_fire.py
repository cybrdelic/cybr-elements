from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, label, gaussian_filter1d
from scipy.spatial import cKDTree
from skimage.morphology import skeletonize
root=Path(__file__).resolve().parent
art=np.array(Image.open(root.parent/'outputs/cybrdelic-type/exploration-v6/cybrdelic-brandmark-refined.png').convert('L'))
for variant,(top,bottom) in enumerate([(95,535),(585,1005)],1):
    mask=art[top:bottom,20:1005]<100
    labs,n=label(mask)
    for j in range(1,n+1):
        ys,xs=np.where(labs==j)
        if len(xs)<35 or (xs.mean()<85 and ys.mean()<130):mask[labs==j]=False
    ys,xs=np.where(mask); x0,x1=xs.min(),xs.max()+1;y0,y1=ys.min(),ys.max()+1
    mask=mask[y0:y1,x0:x1]
    scale=8.05/mask.shape[1]
    sk=skeletonize(mask); coords=np.argwhere(sk); nodes={tuple(p):i for i,p in enumerate(coords)}
    adj=[[] for _ in coords]
    for i,(y,x) in enumerate(coords):
        for dy,dx in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
            j=nodes.get((y+dy,x+dx))
            if j is not None:adj[i].append(j)
    seen=set(); strokes=[]
    while len(seen)<len(coords):
        candidates=[i for i in range(len(coords)) if i not in seen]
        start=min(candidates,key=lambda i:coords[i,1]+.1*coords[i,0])
        walk=[start];seen.add(start);stack=[(start,iter(sorted(adj[start],key=lambda j:coords[j,1])))]
        while stack:
            i,it=stack[-1]
            j=next(it,None)
            if j is None:
                stack.pop()
                if stack:walk.append(stack[-1][0])
            elif j not in seen:
                seen.add(j);walk.append(j);stack.append((j,iter(sorted(adj[j],key=lambda k:coords[k,1]))))
        if len(walk)>2:strokes.append(coords[walk])
    lengths=[np.linalg.norm(np.diff(s,axis=0),axis=1).sum() for s in strokes]
    time=0.;ts=[];ps=[];em=[];first=np.full(mask.shape,np.inf)
    for s,l in zip(strokes,lengths):
        if ps:
            for u in np.linspace(0,1,12,endpoint=False):
                ts.append(time+u*.07);ps.append(ps[-1]*(1-u)+s[0]*u);em.append(0)
            time+=.07
        d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(s,axis=0),axis=1))]
        duration=(12.8-.07*(len(strokes)-1))*l/sum(lengths)
        for p,t in zip(s,time+d/max(d[-1],1)*duration):
            ts.append(t);ps.append(p);em.append(1);first[tuple(p)]=min(first[tuple(p)],t)
        time+=duration
    points=np.asarray(ps,float);points[:,1]=(points[:,1]-mask.shape[1]/2)*scale;points[:,0]=(mask.shape[0]-points[:,0])*scale+.43
    points=points[:,::-1]
    # Arrival at each gas-line cross section follows the moving skeleton nozzle.
    finite=np.argwhere(np.isfinite(first)); _,near=cKDTree(finite).query(np.indices(mask.shape).reshape(2,-1).T)
    arrival=first[tuple(finite[near].T)].reshape(mask.shape)
    # Sample the exact artwork into the physical x/z simulation plane.
    gx=np.linspace(-5.25,5.25,512);gz=np.linspace(0,5.8,320)
    xx,zz=np.meshgrid(gx,gz)
    ix=np.rint(xx/scale+mask.shape[1]/2).astype(int);iy=np.rint(mask.shape[0]-(zz-.43)/scale).astype(int)
    valid=(ix>=0)&(ix<mask.shape[1])&(iy>=0)&(iy<mask.shape[0]);ix=ix.clip(0,mask.shape[1]-1);iy=iy.clip(0,mask.shape[0]-1)
    supply=mask[iy,ix]*valid
    at=np.where(supply,arrival[iy,ix]+.08,1e5)
    np.savez(root/f'brand-fire-{variant:02}.npz',times=ts,points=points,emit=em,arrival=at.astype('f'),supply=supply.astype('f'))
    print(f'{variant:02}: {len(strokes)} skeleton strokes, {time:.2f}s physical writing, silhouette {mask.shape}')

src=(root/'render_handprint_fire.py').read_text()
src=src.replace('from handprint_motion import pose as nozzle_pose, turn_rate as nozzle_turn, WRITE, START, MODE','from brand_fire_motion import pose as nozzle_pose, turn_rate as nozzle_turn, WRITE, START, MODE, VARIANT, DATA')
src=src.replace("ROOT/'handprint-fire-frames'","ROOT/f'brand-fire-{VARIANT}-frames'")
src=src.replace('10.5,1.2,4.2','10.5,1.2,5.8')
src=src.replace('reservoir=torch.zeros(shape,device=device)',"reservoir=torch.zeros(shape,device=device)\narrival=torch.tensor(DATA['arrival'],device=device)[:,None,:]\nbrand_supply=torch.tensor(DATA['supply'],device=device)[:,None,:]*torch.exp(-(y/.055)**2)\n")
src=src.replace('torch.maximum(reservoir,line,out=reservoir)',"deposit=brand_supply*((arrival<=t)&(arrival>t-dt)).float()*.42\n    torch.maximum(reservoir,deposit,out=reservoir)")
src=src.replace("'cybrdelic-handprint-fire.mp4'","f'cybrdelic-brand-{VARIANT}-fire.mp4'")
src=src.replace('4.2-z[:,0,0]','5.8-z[:,0,0]').replace('1.8+view_height/2,1.8-view_height/2','2.35+view_height/2,2.35-view_height/2').replace('vz/4.2','vz/5.8').replace('(3.75-vz)/.60','(5.35-vz)/.60')
src=src.replace("if frame in [239,329,TOTAL-1]:","if False:")
src=src.replace("ROOT/'handprint-fire-report.json'","ROOT/f'brand-fire-{VARIANT}-report.json'")
(root/'render_brand_fire.py').write_text(src)
