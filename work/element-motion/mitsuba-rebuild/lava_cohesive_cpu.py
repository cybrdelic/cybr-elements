"""CPU cohesive crust over a rising molten foundation.

An XPBD membrane with breakable welds and flexion constraints, gravity,
foundation contact and viscous surface drag. The foundation is a prescribed
inflation of the earlier lava volume; there is no two-way fluid coupling.
"""
from pathlib import Path
import os,time,json,argparse
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='2')
import numpy as np
from scipy.ndimage import gaussian_filter,distance_transform_edt,binary_fill_holes,map_coordinates
from scipy.spatial import Delaunay,cKDTree
from scipy.sparse import coo_matrix,diags
from numba import njit
from lava_skin import normals

R=Path(__file__).resolve().parent/'lava-focus'
O=R/'cohesive'; O.mkdir(exist_ok=True)

def smooth(x):
    x=np.clip(x,0,1);return x*x*(3-2*x)

def noise(p,freq,seed):
    field=np.random.default_rng(seed).normal(size=(48,48,48))
    return map_coordinates(field,(p*freq+17).T,order=3,mode='wrap')

@njit(cache=True)
def sample(h,lo,step,x,y):
    a=(x-lo[0])/step;b=(y-lo[1])/step
    i=max(0,min(h.shape[0]-2,int(a)));j=max(0,min(h.shape[1]-2,int(b)))
    u=max(0.,min(1.,a-i));v=max(0.,min(1.,b-j))
    return (1-u)*(1-v)*h[i,j]+u*(1-v)*h[i+1,j]+(1-u)*v*h[i,j+1]+u*v*h[i+1,j+1]

@njit(cache=True)
def distances(x,edges,rest,compliance,lam,dt,active):
    alpha=compliance/(dt*dt)
    for k in range(len(edges)):
        if not active[k]:continue
        i,j=edges[k];d=x[i]-x[j];length=np.sqrt((d*d).sum())
        if length<1e-12:continue
        dl=(-(length-rest[k])-alpha*lam[k])/(2+alpha)
        lam[k]+=dl;delta=d*(dl/length)
        x[i]+=delta;x[j]-=delta

@njit(cache=True)
def solve(x,structural,lengths,welds,bends,bendlength,threshold,h,lo,gridstep,steps,drive,inflate):
    dt=1/180.;vel=np.zeros_like(x)
    weld_active=np.ones(len(welds),np.bool_);stretch_active=np.ones(len(structural),np.bool_)
    zero=np.zeros(len(welds));history=np.zeros((steps,4));initial=x.copy()
    capture_steps=np.array([0,steps//3,steps*2//3,steps-1]);captures=np.zeros((4,len(x),3));capture_active=np.zeros((4,len(welds)),np.bool_)
    for frame in range(steps):
        t=(frame+1)*dt;u=min(1.,t/.8);u=u*u*(3-2*u);fraction=1-inflate+inflate*u
        previous=x.copy();vel*=.985;vel[:,2]-=9.81*dt
        # Substrate drag advects skin forward; decreasing flow speed makes
        # the leading skin compress while inflation supplies tensile load.
        for i in range(len(x)):
            surface=sample(h,lo,gridstep,x[i,0],x[i,1])*fraction+.004
            if x[i,2]-surface<.012:
                target=drive*max(.02,1-(x[i,0]+1.05)/1.8)
                vel[i,0]+=(target-vel[i,0])*.14
                vel[i,1]+=(.018*np.sin(5*x[i,0])-vel[i,1])*.06
        x+=vel*dt
        ls=np.zeros(len(structural));lw=np.zeros(len(welds));lb=np.zeros(len(bends))
        for iteration in range(9):
            distances(x,structural,lengths,8e-9,ls,dt,stretch_active)
            distances(x,bends,bendlength,8e-5,lb,dt,weld_active)
            # Failure is irreversible and depends on the separation the
            # membrane/foundation forces demand at a cohesive interface.
            for k in range(len(welds)):
                if weld_active[k] and frame>10:
                    i,j=welds[k];d=x[i]-x[j]
                    if (d*d).sum()>threshold[k]*threshold[k]:weld_active[k]=False
            distances(x,welds,zero,1e-10,lw,dt,weld_active)
            for i in range(len(x)):
                surface=sample(h,lo,gridstep,x[i,0],x[i,1])*fraction+.004
                if x[i,2]<surface:x[i,2]=surface
        vel=(x-previous)/dt
        maximum=0.;penetration=0.
        for i in range(len(x)):
            speed=np.sqrt((vel[i]*vel[i]).sum());maximum=max(maximum,speed)
            if speed>1.3:vel[i]*=1.3/speed
            surface=sample(h,lo,gridstep,x[i,0],x[i,1])*fraction+.004
            penetration=max(penetration,surface-x[i,2])
        history[frame]=np.array([t,(~weld_active).sum(),maximum,penetration])
        for ci in range(4):
            if frame==capture_steps[ci]:captures[ci]=x;capture_active[ci]=weld_active
    return x,weld_active,history,initial,captures,capture_active

def foundation():
    source=np.load(R/'refined-lobed-02.npz');v=source['v'];f=source['f'];s=.006
    lo=v[:,:2].min(0)-.035;hi=v[:,:2].max(0)+.035;shape=np.ceil((hi-lo)/s).astype(int)+1
    h=np.full(shape,-1.);ix=np.rint((v[:,:2]-lo)/s).astype(int)
    np.maximum.at(h,tuple(ix.T),v[:,2]);known=h>-.1
    _,nearest=distance_transform_edt(~known,return_indices=True);h[~known]=h[tuple(nearest[:,~known])]
    mask=binary_fill_holes(gaussian_filter(known.astype(float),1.4)>.15)
    h=gaussian_filter(h,3.5);edge=distance_transform_edt(mask)*s
    # A rounded, cooled perimeter avoids a glowing vertical cut slab.
    h=np.maximum(0,h)*smooth(edge/.035)
    xx,yy=np.meshgrid(lo[0]+np.arange(shape[0])*s,lo[1]+np.arange(shape[1])*s,indexing='ij')
    grid=np.c_[xx.ravel(),yy.ravel(),h.ravel()]
    a=np.arange((shape[0]-1)*shape[1]).reshape(shape[0]-1,shape[1])[:,:-1].ravel()
    triangles=np.concatenate([np.c_[a,a+shape[1],a+1],np.c_[a+1,a+shape[1],a+shape[1]+1]])
    triangles=triangles[mask.ravel()[triangles].all(1)]
    unique,inv=np.unique(triangles,return_inverse=True);top=grid[unique];tri=inv.reshape(-1,3);n=len(top)
    edges=np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]]);_,inverse,count=np.unique(np.sort(edges,axis=1),axis=0,return_inverse=True,return_counts=True);boundary=edges[count[inverse]==1]
    ed=edge.ravel()[unique]
    lower=top.copy();lower[:,2]=-.025*smooth(ed/.07)
    side=np.concatenate([np.c_[boundary[:,0],boundary[:,0]+n,boundary[:,1]+n],np.c_[boundary[:,0],boundary[:,1]+n,boundary[:,1]]])
    faces=np.concatenate([tri,tri[:,[0,2,1]]+n,side]);body=np.concatenate([top,lower]);normal=normals(body,faces)
    # The exposed margin is older than the sheltered molten interior.
    top_temp=920+(1450-920)*smooth(ed/.17)
    temperature=np.r_[top_temp,np.full(n,840.)]
    return h,mask,edge,lo,s,body,faces,normal,temperature

def crust_setup(h,mask,edge,lo,s,spacing,inflate,strength):
    rng=np.random.default_rng(17201)
    xs=np.arange(lo[0]+.02,lo[0]+h.shape[0]*s-.02,spacing)
    ys=np.arange(lo[1]+.02,lo[1]+h.shape[1]*s-.02,spacing*np.sqrt(3)/2)
    xx,yy=np.meshgrid(xs,ys,indexing='ij');xx[:,::2]+=spacing*.5
    uv=np.c_[xx.ravel(),yy.ravel()]+rng.uniform(-.22,.22,(xx.size,2))*spacing
    coords=((uv-lo)/s).T
    inside=map_coordinates(edge,coords,order=1,mode='constant')>.013;uv=uv[inside]
    tri=Delaunay(uv).simplices
    centroid=uv[tri].mean(1);tri=tri[map_coordinates(edge,((centroid-lo)/s).T,order=1,mode='constant')>.011]
    # Reject long triangulation bridges across concave margins.
    tri=tri[np.linalg.norm(uv[tri[:,0]]-uv[tri[:,1]],axis=1)<spacing*2.]
    e1=uv[tri[:,1]]-uv[tri[:,0]];e2=uv[tri[:,2]]-uv[tri[:,0]];orientation=e1[:,0]*e2[:,1]-e1[:,1]*e2[:,0]
    tri[orientation<0]=tri[orientation<0][:,[0,2,1]]
    v=np.c_[uv,map_coordinates(h,((uv-lo)/s).T,order=1)*(1-inflate)+.004]
    v[:,2]+=.0002*noise(v,34,813)
    x=v[tri].reshape(-1,3);render_faces=np.arange(len(x)).reshape(-1,3)
    structural=np.concatenate([render_faces[:,[0,1]],render_faces[:,[1,2]],render_faces[:,[2,0]]]);length=np.linalg.norm(x[structural[:,0]]-x[structural[:,1]],axis=1)
    shared={};welds=[];bends=[];locations=[]
    for face,corners in enumerate(tri):
        for j in range(3):
            va,vb=corners[j],corners[(j+1)%3];key=tuple(sorted([int(va),int(vb)]))
            la=face*3+j;lb=face*3+(j+1)%3;op=face*3+(j+2)%3
            if key in shared:
                aa,bb,oo,oldva=shared.pop(key)
                if oldva!=va:aa,bb=bb,aa
                welds.extend([[la,aa],[lb,bb]]);bends.extend([[op,oo],[op,oo]])
                mid=(v[va]+v[vb])*.5;locations.extend([mid,mid])
            else:shared[key]=(la,lb,op,va)
    welds=np.array(welds,dtype=np.int32);bends=np.array(bends,dtype=np.int32)
    loc=np.array(locations);weak=.75+.45*smooth(noise(loc,9,125)+.45)
    threshold=strength*weak
    return x,render_faces,structural,length,welds,bends,np.linalg.norm(x[bends[:,0]]-x[bends[:,1]],axis=1),threshold

def clip_vents(v,r,tri,opening,threshold):
    """Clip at the continuous scalar contour, rather than dropping faces."""
    inside=opening<threshold
    edges=np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]])
    cross=edges[inside[edges[:,0]]!=inside[edges[:,1]]]
    cross=np.unique(np.sort(cross,axis=1),axis=0)
    t=(threshold-opening[cross[:,0]])/(opening[cross[:,1]]-opening[cross[:,0]])
    count=len(v);lookup={tuple(pair):i+count for i,pair in enumerate(cross)}
    v=np.concatenate([v,v[cross[:,0]]*(1-t[:,None])+v[cross[:,1]]*t[:,None]])
    r=np.concatenate([r,r[cross[:,0]]*(1-t[:,None])+r[cross[:,1]]*t[:,None]])
    flags=inside[tri];keep=tri[flags.all(1)];partial=tri[flags.any(1)&~flags.all(1)];new=[]
    for face in partial:
        polygon=[]
        for j in range(3):
            a,b=int(face[j]),int(face[(j+1)%3])
            if inside[a]:polygon.append(a)
            if inside[a]!=inside[b]:polygon.append(lookup[tuple(sorted([a,b]))])
        for j in range(1,len(polygon)-1):new.append([polygon[0],polygon[j],polygon[j+1]])
    return v,r,np.concatenate([keep,np.array(new,dtype=np.int32)])

def shell_mesh(x,f,welds,active,rest,detail=None):
    # Merge only intact cohesive interfaces, keeping both banks of every
    # tear as independent boundaries with their own physical side walls.
    parent=np.arange(len(x))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,j in welds[active]:
        a,b=find(i),find(j)
        if a!=b:parent[b]=a
    root=np.array([find(i) for i in range(len(x))]);_,inv=np.unique(root,return_inverse=True);n=inv.max()+1
    v=np.zeros((n,3));r=np.zeros_like(v);count=np.bincount(inv)
    np.add.at(v,inv,x);np.add.at(r,inv,rest);v/=count[:,None];r/=count[:,None];tri=inv[f]
    keep=(tri[:,0]!=tri[:,1])&(tri[:,0]!=tri[:,2])&(tri[:,1]!=tri[:,2]);tri=tri[keep]
    for _ in range(2):
        edges=np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]]);unique,ix=np.unique(np.sort(edges,axis=1),axis=0,return_inverse=True);mid=ix.reshape(3,-1).T+len(v)
        v=np.concatenate([v,v[unique].mean(1)]);r=np.concatenate([r,r[unique].mean(1)])
        a,b,c=tri.T;ab,bc,ca=mid.T;tri=np.concatenate([np.c_[a,ab,ca],np.c_[ab,b,bc],np.c_[ca,bc,c],np.c_[ab,bc,ca]])
    normal=normals(v,tri)
    height=.0013*noise(r,40,28)+.00055*noise(r,112,913)
    if detail is not None:
        h,lo,s=detail
        old=np.load(R/'refined-lobed-02.npz');ov=old['v'];select=(ov[:,2]>0)&(old['normal'][:,2]>.12)
        locations=ov[select];tree=cKDTree(locations[:,:2]);d,ix=tree.query(r[:,:2],k=3,workers=1)
        weights=1/np.maximum(d,.0015)**3;weights/=weights.sum(1)[:,None]
        old_z=(locations[ix,2]*weights).sum(1)
        coarse=map_coordinates(h,((r[:,:2]-lo)/s).T,order=1,mode='nearest')
        residual=np.clip(old_z-coarse,-.006,.025)
        height+=.009+residual
        # Fine, authored cooling vents from the preferred surface become
        # physical holes through the shell, not orange surface triangles.
        opening=(old['opening'][select][ix]*weights).sum(1)
    v+=normal*height[:,None]
    if detail is not None:
        v,r,tri=clip_vents(v,r,tri,opening,.48)
        # Relax the contour at the mesh scale, retaining broad tear shape.
        edges=np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]]);unique,counts=np.unique(np.sort(edges,axis=1),axis=0,return_counts=True);boundary=unique[counts==1]
        row=np.r_[boundary[:,0],boundary[:,1]];col=np.r_[boundary[:,1],boundary[:,0]]
        adj=coo_matrix((np.ones(len(row)),(row,col)),shape=(len(v),len(v))).tocsr();degree=np.asarray(adj.sum(1)).ravel();select=degree==2
        for _ in range(4):
            mean=adj@v;v[select]=.65*v[select]+.35*mean[select]/2
        normal=normals(v,tri)
    thick=.004+.002*smooth(noise(r,7,19)+.5)
    lower=v-normal*thick[:,None];n=len(v)
    edges=np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]]);_,ix,count=np.unique(np.sort(edges,axis=1),axis=0,return_inverse=True,return_counts=True);border=edges[count[ix]==1]
    side=np.concatenate([np.c_[border[:,0],border[:,0]+n,border[:,1]+n],np.c_[border[:,0],border[:,1]+n,border[:,1]]])
    faces=np.concatenate([tri,tri[:,[0,2,1]]+n,side]);vertices=np.concatenate([v,lower]);material=np.concatenate([r,r])
    temperature=np.r_[960+90*smooth(noise(r,5,183)+.5),np.full(n,1250.)]
    return vertices,faces,normals(vertices,faces),temperature,material

def main(name,steps,spacing,strength,drive,inflate):
    start=time.time();h,mask,edge,lo,s,bv,bf,bn,bt=foundation()
    x,faces,structural,lengths,welds,bends,bl,threshold=crust_setup(h,mask,edge,lo,s,spacing,inflate,strength)
    print(json.dumps({'vertices':len(x),'triangles':len(faces),'welds':len(welds),'steps':steps}),flush=True)
    x,active,history,rest,captures,capture_active=solve(x,structural,lengths,welds,bends,bl,threshold,h,lo,s,steps,drive,inflate)
    assert np.isfinite(x).all() and np.isfinite(history).all()
    assert np.all(np.diff(history[:,1])>=0) and history[:,3].max()<1e-6
    np.savez_compressed(O/f'{name}-mechanics.npz',x=x,f=faces,rest=rest,welds=welds,active=active,history=history,captures=captures,capture_active=capture_active)
    sv,sf,sn,st,sr=shell_mesh(x,faces,welds,active,rest)
    combined=dict(v=np.concatenate([bv,sv]).astype('f4'),f=np.concatenate([bf,sf+len(bv)]).astype('i4'),normal=np.concatenate([bn,sn]).astype('f4'),temperature=np.r_[bt,st].astype('f4'),rest=np.concatenate([bv,sr]).astype('f4'),component=np.r_[np.zeros(len(bv)),np.ones(len(sv))].astype('u1'))
    output=O/f'{name}.npz';np.savez_compressed(output,**combined)
    report={'device':'CPU','method':'XPBD elastic triangles, irreversible cohesive weld failure, compliant flexion, gravity, viscous drag and unilateral foundation contact','steps':steps,'dt':1/180,'simulationSeconds':steps/180,'mechanicalTriangles':len(faces),'brokenWeldFraction':float((~active).mean()),'maxSpeedBeforeCap':float(history[:,2].max()),'contactPenetrationM':float(history[:,3].max()),'renderVertices':len(combined['v']),'renderTriangles':len(combined['f']),'wallSeconds':round(time.time()-start,2),'settings':{'spacing':spacing,'cohesiveSeparationM':strength,'surfaceDriveMps':drive,'inflationFraction':inflate},'limits':['Foundation inflation is kinematic, with no crust-to-fluid force feedback','Flexion uses opposite-vertex distances, not a full shell finite-element law','Crust microrelief and temperature history are authored; not calibrated basalt mechanics','No crust self-contact solver yet']}
    output.with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='shell-01');ap.add_argument('--steps',type=int,default=180);ap.add_argument('--spacing',type=float,default=.024);ap.add_argument('--strength',type=float,default=.0022);ap.add_argument('--drive',type=float,default=.09);ap.add_argument('--inflate',type=float,default=.32);a=ap.parse_args();main(a.name,a.steps,a.spacing,a.strength,a.drive,a.inflate)
