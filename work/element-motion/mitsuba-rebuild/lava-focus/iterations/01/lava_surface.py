"""Flow-attached, multiscale basalt relief over the CPU viscous volume.

This is a procedural VFX skin informed by particle deformation and heat,
not a microscopic fracture simulation. It replaces neither the bulk motion
nor its thermal viscosity. Cracks are geometric depressions exposing depth
in the thermal boundary layer, not a flat orange Voronoi color texture.
"""
from pathlib import Path
import os,time,json,argparse
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['CUDA_VISIBLE_DEVICES']='-1'
import numpy as np
from scipy.ndimage import gaussian_filter,map_coordinates
from scipy.spatial import cKDTree
from scipy.special import erf
from skimage.measure import marching_cubes
from PIL import Image
from lava_skin import columns,normals
R=Path(__file__).resolve().parent/'lava-focus'

def signed_volume(v,f):return float(np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))/6)
def noise(p,frequency,seed):
 field=np.random.default_rng(seed).normal(0,1,(48,48,48)).astype('f4');return map_coordinates(field,(p*frequency+17).T,order=3,mode='wrap',prefilter=True)
def smooth(x):x=np.clip(x,0,1);return x*x*(3-2*x)

def material_lut():
 path=R/'thermal-lut.npz'
 if path.exists():return np.load(path)
 ages=np.linspace(.8,5.,128);cores=np.linspace(1340,1470,24);aa,cc=np.meshgrid(ages,cores,indexing='ij');skin,phase,depth,_,_,_,_=columns(aa.ravel(),cc.ravel());np.savez_compressed(path,ages=ages,cores=cores,skin=skin.reshape(aa.shape));return np.load(path)

def microtexture():
 path=R/'basalt-micro.png'
 if path.exists():return
 n=1024;rng=np.random.default_rng(775);height=gaussian_filter(rng.normal(0,1,(n,n)),.65)*.05
 # Small quenched-gas pits; a bounded heavy tail keeps large vesicles rare.
 for i in range(17000):
  x,y=rng.integers(9,n-9,2);r=min(5.5,.65*(1+rng.pareto(2.3)));rr=int(np.ceil(r))+1;xx,yy=np.meshgrid(np.arange(-rr,rr+1),np.arange(-rr,rr+1));q=(xx*xx+yy*yy)/(r*r);pit=-np.sqrt(np.maximum(0,1-q))*.13;height[y-rr:y+rr+1,x-rr:x+rr+1]+=pit
 height=np.clip(height+.65,0,1);Image.fromarray((height*65535).astype('uint16')).save(path)

def main(frame=59,detail=.004):
 start=time.time();a=np.load(R/f'flow-{frame:04}.npz');p=a['p'];rest=a['rest'];radius=float(a['spacing'])*1.65;lo=np.floor((p.min(0)-radius*3)/detail)*detail;shape=np.ceil((p.max(0)+radius*3-lo)/detail).astype(int)+1;assert np.prod(shape)<18000000;grid=np.zeros(shape,dtype='f4');q=(p-lo)/detail;ib=np.floor(q).astype(int);frac=q-ib
 for i in [0,1]:
  for j in [0,1]:
   for k in [0,1]:
    ix=ib+[i,j,k];w=(frac[:,0] if i else 1-frac[:,0])*(frac[:,1] if j else 1-frac[:,1])*(frac[:,2] if k else 1-frac[:,2]);np.add.at(grid,tuple(ix.T),w)
 grid=gaussian_filter(grid,radius/detail,mode='constant');target=len(p)*float(a['volume']);left=float(grid.max())*.002;right=float(grid.max())*.8
 for it in range(9):
  level=(left+right)/2;v,f,_,_=marching_cubes(grid,level,spacing=(detail,)*3);v+=lo;volume=signed_volume(v,f)
  if volume<0:f=f[:,[0,2,1]];volume=-volume
  if volume>target:left=level
  else:right=level
 base_v=v.copy();base_n=normals(v,f);distance,ix=cKDTree(p).query(v,k=8,workers=1);w=1/np.maximum(distance,.008)**3;w/=w.sum(1)[:,None];material=(rest[ix]*w[...,None]).sum(1);bulk=(a['temperature'][ix]*w).sum(1)
 # Least-squares deformation of material neighborhoods supplies a stable
 # mechanical cue for relief amplitude and tear width.
 _,nn=cKDTree(rest).query(rest,k=18,workers=1);d0=rest[nn]-rest[:,None,:];d1=p[nn]-p[:,None,:];A=np.einsum('nki,nkj->nij',d0,d0);B=np.einsum('nki,nkj->nij',d1,d0);F=B@np.linalg.inv(A+np.eye(3)[None]*1e-7);singular=np.linalg.svd(F,compute_uv=False);compression=np.clip(1-singular[:,-1],0,.9);tension=np.clip(singular[:,0]-1,0,2);comp=(compression[ix]*w).sum(1);tens=(tension[ix]*w).sum(1)
 warp=noise(material,4.0,61);large=noise(material,9.0,33);medium=noise(material,29.,813);small=noise(material,92.,731)
 # Broad folds, shorter secondary corrugations, and fine fractured relief
 # occupy different scales. Every coordinate is attached to the matter.
 phase=material[:,0]*135+2.8*np.sin(material[:,1]*12)+1.8*warp+.5*large
 ridge=(.5+.5*np.sin(phase))**2.7;fine_ridge=(.5+.5*np.sin(phase*2.07+medium*.8))**3
 wrinkle=(.003+.013*comp)*ridge+.0022*fine_ridge;rough=.0018*medium+.00065*small
 cell=np.array([.14,.22,.13]);low=np.floor(rest.min(0)/cell).astype(int)-2;high=np.ceil(rest.max(0)/cell).astype(int)+2;seeds=np.stack(np.meshgrid(*[np.arange(low[j],high[j]+1) for j in range(3)],indexing='ij'),axis=-1).reshape(-1,3);rng=np.random.default_rng(588);sites=(seeds+rng.uniform(.08,.92,seeds.shape))*cell
 ds,isite=cKDTree(sites).query(material,k=2,workers=1);den=np.linalg.norm(sites[isite[:,1]]-sites[isite[:,0]],axis=1);border=(ds[:,1]**2-ds[:,0]**2)/(2*np.maximum(den,1e-6));strength=rng.uniform(.08,.9,len(sites))[isite[:,0]];width=.0018+.0065*smooth(tens*.65)*(.4+.6*smooth(large+.5));activation=smooth((tens+.12-strength)/.5);opening=smooth(1-border/width)*activation
 clinker=smooth(border/.028)*(.005+.003*np.clip(large,-1,1));height=clinker+wrinkle+rough-opening**1.5*.017
 # Contact-side detail remains shallow instead of cutting a glowing flat
 # underside into a fabricated slab.
 topness=smooth((base_n[:,2]+.3)/.9);height*=.18+.82*topness
 v=base_v+base_n*height[:,None];center=v.mean(0);current=signed_volume(v,f);scale=(target/current)**(1/3);v=center+(v-center)*scale;normal=normals(v,f)
 lut=material_lut();age=1.85+3.0*np.clip((1460-bulk)/95,0,1);coordinates=np.array([(age-.8)/(5-.8)*127,(bulk-1340)/(1470-1340)*23]);skin_temp=map_coordinates(lut['skin'],coordinates,order=1,mode='nearest');penetration=.017*opening**2.2;boundary=2*np.sqrt(5.0e-7*age);temperature=skin_temp+(bulk-skin_temp)*erf(penetration/np.maximum(boundary,1e-6));temperature=np.clip(temperature,600,1470)
 np.savez_compressed(R/f'surface-{frame:04}.npz',v=v.astype('f4'),f=f.astype('i4'),normal=normal.astype('f4'),rest=material.astype('f4'),temperature=temperature.astype('f4'),opening=opening.astype('f4'),compression=comp.astype('f4'),tension=tens.astype('f4'),bulk=bulk.astype('f4'))
 edges=np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1);_,counts=np.unique(edges,axis=0,return_counts=True);assert (counts==2).all();microtexture();report={'frame':frame,'seconds':round(time.time()-start,2),'grid':shape.tolist(),'vertices':len(v),'triangles':len(f),'volumeTarget':target,'volumeActual':signed_volume(v,f),'relativeVolumeError':abs(signed_volume(v,f)/target-1),'closed':True,'openingFractionAboveHalf':float((opening>.5).mean()),'temperatureK':np.quantile(temperature,[0,.1,.5,.9,.99,1]).tolist(),'compression':np.quantile(comp,[.1,.5,.9]).tolist(),'tension':np.quantile(tens,[.1,.5,.9]).tolist(),'method':'Advected multiscale procedural geometry informed by local deformation and a thermal boundary-layer model','limits':'Relief is a VFX surface model, not resolved crust fracture; volume correction is global.'};(R/f'surface-{frame:04}.json').write_text(json.dumps(report,indent=2));print('SURFACE',json.dumps(report),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--frame',type=int,default=59);ap.add_argument('--spacing',type=float,default=.004);a=ap.parse_args();main(a.frame,a.spacing)
