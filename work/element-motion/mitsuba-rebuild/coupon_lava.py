"""CPU compression/rupture coupon for a thin lava skin over a liquid foundation.

This deliberately tests actual folding geometry before another trail render.
It is a reduced XPBD membrane model, not a complete 3D lava flow solver.
"""
from pathlib import Path
import os,json,time
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['NUMBA_NUM_THREADS']='2'
import numpy as np
from numba import njit
from scipy.ndimage import gaussian_filter
from lava_skin import columns,normals
R=Path(__file__).resolve().parent

@njit(cache=True)
def solve(x,edges,rest_length,kind,uv,frames=190):
 n=len(x);velocity=np.zeros_like(x);state=np.ones(len(edges),dtype=np.int8);dt=1/90.;stats=np.zeros((frames,3));rng=np.arange(n);mass=.0025*2700*.74*.38/n;inv=1/mass
 for f in range(frames):
  previous=x.copy();velocity[:,2]-=.6*dt;velocity*=.968;x+=dt*velocity;progress=min(1.,f/145.);right=.74*(1-.30*progress);shear=max(0.,(f-140)/50)*.018
  lambdas=np.zeros(len(edges))
  for iteration in range(10):
   for e in range(len(edges)):
    if state[e]==0:continue
    a,b=edges[e];d0=x[a,0]-x[b,0];d1=x[a,1]-x[b,1];d2=x[a,2]-x[b,2];distance=np.sqrt(d0*d0+d1*d1+d2*d2);target=rest_length[e];strain=(distance-target)/target
    if kind[e]==0 and f>140 and strain>.075:state[e]=0;continue
    compliance=2e-8 if kind[e]==0 else .0007;alpha=compliance/(dt*dt);dl=(-(distance-target)-alpha*lambdas[e])/(2*inv+alpha);lambdas[e]+=dl;factor=dl*inv/max(distance,1e-12);x[a,0]+=factor*d0;x[a,1]+=factor*d1;x[a,2]+=factor*d2;x[b,0]-=factor*d0;x[b,1]-=factor*d1;x[b,2]-=factor*d2
   for i in range(n):
    # A shallow liquid pressure foundation prevents interpenetration. The
    # reduced coupon uses prescribed support instead of pretending it has
    # solved the unobserved bulk flow.
    bottom=.011+.013*np.exp(-(x[i,1]/.17)**4)
    if x[i,2]<bottom:x[i,2]=bottom
    if uv[i,0]<.001:x[i,0]=0.;x[i,1]=uv[i,1]-.19
    if uv[i,0]>.739:x[i,0]=right;x[i,1]=uv[i,1]-.19+shear*np.sin(uv[i,1]*11)
  velocity=(x-previous)/dt;stats[f,0]=np.sqrt(np.sum(velocity*velocity,axis=1)).max();stats[f,1]=x[:,2].max();stats[f,2]=(state==0).sum()
 return x,velocity,state,stats

def closed_skin(v,f,thickness):
 n=normals(v,f);bottom=v-n*thickness;edges=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]);_,inv,count=np.unique(np.sort(edges,axis=1),axis=0,return_inverse=True,return_counts=True);boundary=edges[count[inv]==1];N=len(v);faces=[f,f[:,[0,2,1]]+N]
 for a,b in boundary:faces.append(np.array([[a,a+N,b+N],[a,b+N,b]]))
 return np.concatenate([v,bottom]),np.concatenate(faces)

def main():
 start=time.time();nx,ny=91,39;xx,yy=np.meshgrid(np.linspace(0,.74,nx),np.linspace(0,.38,ny),indexing='ij');uv=np.stack([xx.ravel(),yy.ravel()],axis=1);v=np.column_stack([uv[:,0],uv[:,1]-.19,np.zeros(nx*ny)]);imperfection=gaussian_filter(np.random.default_rng(513).normal(0,1,(nx,ny)),1.4);v[:,2]=.012+.013*np.exp(-(v[:,1]/.17)**4)+imperfection.ravel()*.00008;rest=v.copy();faces=[];edges=[];kinds=[]
 for i in range(nx):
  for j in range(ny):
   a=i*ny+j
   if i<nx-1:edges.append((a,a+ny));kinds.append(0)
   if j<ny-1:edges.append((a,a+1));kinds.append(0)
   if i<nx-1 and j<ny-1:
    edges.extend([(a,a+ny+1),(a+1,a+ny)]);kinds.extend([0,0]);faces.extend([(a,a+ny,a+1),(a+1,a+ny,a+ny+1)])
   if i<nx-2:edges.append((a,a+2*ny));kinds.append(1)
   if j<ny-2:edges.append((a,a+2));kinds.append(1)
 faces=np.array(faces);edges=np.array(edges);kinds=np.array(kinds);length=np.linalg.norm(v[edges[:,0]]-v[edges[:,1]],axis=1);from projective_skin import solve as implicit_solve
 x,velocity,state,stats=implicit_solve(v,edges,length,kinds,uv);assert np.isfinite(x).all() and stats[:,0].max()<20
 # Rupture opens geometric holes; an emissive texture cannot manufacture
 # them. This coarse coupon removes ruptured triangles, with closed walls.
 lengths={tuple(sorted(pair)):length[i] for i,pair in enumerate(edges) if kinds[i]==0};intact=np.ones(len(faces),bool)
 for j,face in enumerate(faces):
  for a,b in [(face[0],face[1]),(face[1],face[2]),(face[2],face[0])]:
   reference=lengths[tuple(sorted((a,b)))];strain=np.linalg.norm(x[a]-x[b])/reference-1
   if strain>.09:intact[j]=False
 top_faces=faces[intact];V,F=closed_skin(x,top_faces,.0018);age=3.1-uv[:,0]*.75;temperature,phase,depth,removed,external,received,balance=columns(age,np.full(len(v),1450.));out=R/'coupons/lava';out.mkdir(parents=True,exist_ok=True);np.savez_compressed(out/'skin.npz',v=V,f=F,normal=normals(V,F),temperature=np.tile(temperature,2),phase=np.tile(phase,2),rest=np.tile(rest,(2,1)),uv=np.tile(uv,(2,1)))
 # One closed, smooth molten reservoir lies below the folded surface.
 low=x.copy();low[:,2]=.012+.006*np.exp(-(low[:,1]/.18)**4);MV,MF=closed_skin(low,faces,.022);np.savez_compressed(out/'melt.npz',v=MV,f=MF,normal=normals(MV,MF),temperature=np.full(len(MV),1450.),rest=np.tile(rest,(2,1)),uv=np.tile(uv,(2,1)))
 report={'status':'geometry coupon; not a final effect','reference':'https://www.nps.gov/articles/000/lava-flow-forms.htm','solver':'Implicit sparse projective membrane solve, pressure foundation, compression and tensile rupture','vertices':len(x),'frames':100,'seconds':round(time.time()-start,3),'compression':.30,'maximumSpeed':float(stats[:,0].max()),'heightRange':np.quantile(x[:,2],[0,.1,.5,.9,1]).tolist(),'brokenConstraints':int((state==0).sum()),'removedTriangles':int((~intact).sum()),'thermalBalanceRelativeError':abs(balance)/max(removed,1),'temperatureK':np.quantile(temperature,[0,.5,1]).tolist(),'limitations':['Foundation is prescribed; bulk and skin momentum are not two-way coupled','Distance bending is a reduced shell model','Crack aperture is limited by mesh resolution','Thermal columns include an explicit bending heat sink']};(out/'report.json').write_text(json.dumps(report,indent=2,default=float));print('LAVA_COUPON',json.dumps(report,default=float))
if __name__=='__main__':main()
