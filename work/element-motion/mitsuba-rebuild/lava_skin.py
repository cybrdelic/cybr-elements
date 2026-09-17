"""Subgrid thermal columns and separated crust shells on fresh lava motion.

The columns resolve the cooling layer that the centimetre MPM grid cannot.
Radiation, convection, latent heat and an explicitly recorded bending heat
sink drive temperature. The skin uses a reduced foundation-shell fracture
model; it does not feed shell contact impulses back into the bulk MPM.
"""
from pathlib import Path
import os,sys,json,time,argparse
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['NUMBA_NUM_THREADS']='2'
import numpy as np
from numba import njit
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent

@njit(cache=True)
def phase(h):
 if h<0:return 1150+h/1200.,1.
 if h<628000:return 1150+190*h/628000,1-h/628000
 return 1340+(h-628000)/1200,0.

@njit(cache=True)
def columns(age,bulk,flux=650000.):
 n=len(age);layers=14;dz=.0004;rho=2700.;dt=.004;h=np.full((n,layers),796000.);temperature=np.full_like(h,1480.);removed=0.;external=0.;received=0.
 for step in range(int(age.max()/dt)+1):
  t=(step+1)*dt
  for i in range(n):
   if t>age[i]:continue
   for j in range(layers):temperature[i,j]=phase(h[i,j])[0]
   skin=temperature[i,0];natural=.94*5.670374419e-8*(skin**4-293.15**4)+45*(skin-293.15);bending=flux*(1-np.exp(-t/.22));loss=(natural+bending)*dt/(rho*dz)
   actual=min(loss,max(0,h[i,0]+1028220));h[i,0]-=actual;removed+=actual*rho*dz;external+=actual*rho*dz*bending/max(natural+bending,1e-8)
   for j in range(layers-1):
    q=1.6*(temperature[i,j+1]-temperature[i,j])/dz*dt/(rho*dz);h[i,j]+=q;h[i,j+1]-=q
   core=1480+(bulk[i]-1480)*t/max(age[i],dt);q=1.6*(core-temperature[i,-1])/dz*dt/(rho*dz);h[i,-1]+=q;received+=q*rho*dz
 solid=np.zeros_like(h)
 for i in range(n):
  for j in range(layers):temperature[i,j],solid[i,j]=phase(h[i,j])
 balance=(h.sum()-n*layers*796000)*rho*dz+removed-received
 return temperature[:,0],solid[:,0],solid.sum(1)*dz,removed,external,received,balance

def normals(v,f):
 n=np.zeros_like(v);fn=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
 for j in range(3):np.add.at(n,f[:,j],fn)
 return n/np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12)

def run(frame):
 start=time.time();a=np.load(R/'mesh/lava'/f'{frame:04}.npz');v=a['v'];f=a['f'];rest=a['rest'];normal=a['normal'];age=np.maximum((frame+1)/30-a['birth'],0);t,solid,depth,removed,external,received,balance=columns(age,a['temperature']);assert np.isfinite(t).all() and t.min()>250
 # Spatially stable nucleation sites follow material coordinates, so the
 # fragments cannot swim across the moving liquid like a texture.
 quant=np.floor(rest/.10).astype(int);_,seed_ix=np.unique(quant,axis=0,return_index=True);sites=rest[seed_ix];_,group=cKDTree(sites).query(rest[f].mean(1));strain=np.linalg.svd(a['deformation'],compute_uv=False);tension=np.maximum(np.log(strain).max(1),0);compression=np.maximum(-np.log(strain).min(1),0);cold=solid[f].mean(1)>.48
 vv=[];ff=[];tt=[];ss=[];rr=[];groups=0;crack_openings=[]
 for g in np.unique(group[cold]):
  faces=f[(group==g)&cold];unique,inverse=np.unique(faces,return_inverse=True);top=v[unique].copy();nn=normal[unique];center=top.mean(0);temp=t[unique];thermal=np.maximum(0,(1340-temp)*2.8e-5);opening=np.clip(tension[unique].mean()+thermal.mean()-.006,0,.065);top=center+(top-center)*(1-opening);thickness=np.maximum(.0003,depth[unique]);top+=nn*(thickness*.5)[:,None]
  # A compressed bonded skin buckles; amplitude follows excess shortening.
  shorten=np.maximum(0,compression[unique]-.007);wave=.065;amplitude=np.minimum(.008,wave/(2*np.pi)*np.sqrt(shorten));top+=nn*(amplitude*np.sin(rest[unique,0]*2*np.pi/wave))[:,None]
  bottom=top-nn*thickness[:,None];local=inverse.reshape(-1,3);edges=np.concatenate([local[:,[0,1]],local[:,[1,2]],local[:,[2,0]]]);sorted_edges=np.sort(edges,axis=1);_,inverse_edges,counts=np.unique(sorted_edges,axis=0,return_inverse=True,return_counts=True);boundary=edges[counts[inverse_edges]==1];n=len(unique);shell=[local,local[:,[0,2,1]]+n]
  for e0,e1 in boundary:shell.append(np.array([[e0,e0+n,e1+n],[e0,e1+n,e1]]))
  offset=sum(len(q) for q in vv);vv.append(np.concatenate([top,bottom]));ff.append(np.concatenate(shell)+offset);tt.append(np.concatenate([temp,temp]));ss.append(np.concatenate([solid[unique],solid[unique]]));rr.append(np.concatenate([rest[unique],rest[unique]]));groups+=1;crack_openings.append(float(opening))
 if not vv:raise RuntimeError('No solid surface: do not render a claimed crust')
 V=np.concatenate(vv);F=np.concatenate(ff).astype('i4');N=normals(V,F);out=R/'mesh/lava'/f'skin-{frame:04}.npz';np.savez_compressed(out,v=V,f=F,normal=N,temperature=np.concatenate(tt),phase=np.concatenate(ss),rest=np.concatenate(rr))
 area=np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1).sum()*.5;report={'model':'14-layer finite-volume enthalpy columns + reduced crust foundation shells','frame':frame,'seconds':round(time.time()-start,3),'columnDepthM':.0056,'crustGroups':groups,'surfaceTemperatureK':np.quantile(t,[0,.1,.5,.9,1]).tolist(),'solidSurfaceFraction':float(cold.mean()),'crackOpeningStrain':np.quantile(crack_openings,[0,.5,1]).tolist(),'columnEnergyRelativeError':abs(balance)/max(removed,1),'surfaceAreaM2':float(area),'removedEnergyApproxJ':removed/len(v)*area,'externalBendingSinkApproxJ':external/len(v)*area,'heatFromBulkApproxJ':received/len(v)*area,'limits':['Local columns ignore lateral heat diffusion','Reduced shell foundation; no shell-to-bulk contact feedback','External bending heat sink is authored and explicitly accounted; cooling is not solely ambient radiation']};out.with_suffix('.json').write_text(json.dumps(report,indent=2,default=float));print('LAVA_SKIN',json.dumps(report,default=float))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--frame',type=int,default=61);a=ap.parse_args();run(a.frame)
