"""CPU rupture study: one connected lava volume, lifted old crust and rafts.

The shape and fracture layout are authored. Surface temperatures come from
thin finite-volume enthalpy columns. This is a material/geometry study, not
a claim of a new validated Navier-Stokes flow simulation.
"""
from pathlib import Path
import os,json,time,argparse,hashlib
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='2')
import numpy as np
from scipy.ndimage import map_coordinates
from scipy.spatial import cKDTree
from skimage.measure import marching_cubes
from numba import njit
from lava_skin import normals,phase
from lava_cohesive_cpu import clip_vents
from lava_lobes_cpu import closed_skin,preview

R=Path(__file__).resolve().parent/'lava-focus';O=R/'breakout';O.mkdir(exist_ok=True)

def smooth(x):
    x=np.clip(x,0,1);return x*x*(3-2*x)

def noise(p,freq,seed):
    field=np.random.default_rng(seed).normal(size=(48,48,48)).astype('f4')
    return map_coordinates(field,(p*freq+19).T,order=3,mode='wrap')

@njit(cache=True)
def film_columns(ages,bulk=1450.):
    layers=128;dz=.0001;rho=2700.;dtmax=.004
    initial=628000.+(bulk-1340.)*1200.;output=np.zeros(len(ages));removed=0.;received=0.;change=0.
    for i in range(len(ages)):
        h=np.full(layers,initial);temp=np.full(layers,bulk);t=0.
        while t<ages[i]:
            dt=min(dtmax,ages[i]-t);t+=dt
            for j in range(layers):temp[j]=phase(h[j])[0]
            q=(.94*5.670374419e-8*(temp[0]**4-293.15**4)+45*(temp[0]-293.15))*dt
            h[0]-=q/(rho*dz);removed+=q
            for j in range(layers-1):
                q=1.6*(temp[j+1]-temp[j])*dt/dz
                h[j]+=q/(rho*dz);h[j+1]-=q/(rho*dz)
            q=1.6*(bulk-temp[-1])*dt/dz;h[-1]+=q/(rho*dz);received+=q
        output[i]=phase(h[0])[0];change+=(h.sum()-layers*initial)*rho*dz
    return output,abs(change+removed-received)/max(removed,1.)

def core_mesh(step):
    lo=np.array([-.92,-.49,-.09]);hi=np.array([.89,.50,.39]);shape=np.ceil((hi-lo)/step).astype(int)+1
    y,z=np.meshgrid(lo[1]+np.arange(shape[1])*step,lo[2]+np.arange(shape[2])*step,indexing='ij')
    sdf=np.empty(shape,'f4')
    lobes=[(np.array([-.36,.10,.075]),np.array([.46,.30,.152]),-.08),
           (np.array([-.015,-.045,.048]),np.array([.40,.24,.125]),-.22),
           (np.array([.335,-.090,.013]),np.array([.32,.190,.098]),.13),
           (np.array([.245,.145,.018]),np.array([.235,.145,.081]),-.24)]
    for i in range(shape[0]):
        x=lo[0]+i*step;field=np.full_like(y,1e3)
        for center,rad,angle in lobes:
            dx=x-center[0];dy=y-center[1];xx=np.cos(angle)*dx+np.sin(angle)*dy;yy=-np.sin(angle)*dx+np.cos(angle)*dy
            d=(np.sqrt((xx/rad[0])**2+(yy/rad[1])**2+((z-center[2])/rad[2])**2)-1)*min(rad)
            # Smooth union gives one volume, including between the lobes.
            k=.032;h=np.maximum(k-abs(field-d),0)/k;field=np.minimum(field,d)-h*h*k*.25
        sdf[i]=field
    v,f,_,_=marching_cubes(sdf,0,spacing=(step,)*3,allow_degenerate=False);v+=lo
    f=f[:,[0,2,1]]
    if np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))/6<0:f=f[:,[0,2,1]]
    n=normals(v,f);rest=v.copy()
    # Surface undulations vary continuously with space and flow direction.
    stretched=v.copy();stretched[:,0]*=.32
    micro=.005*noise(v,12,824)+.00095*noise(stretched,64,932)
    v+=n*micro[:,None]
    return v,f,normals(v,f),rest

def skin_relief(p):
    # A few local compressed lips, each with its own extent and width.
    # No repeating phase is extended across the entire surface.
    relief=np.zeros(len(p));lean=np.zeros(len(p))
    for x,y,length,width,height,curve in [(-.38,.11,.11,.015,.009,1.1),(-.28,.10,.16,.021,.012,1.5),(.24,-.12,.080,.014,.007,2.),(.40,-.10,.11,.021,.009,2.6),(.48,-.065,.055,.010,.005,3.1)]:
        dy=p[:,1]-y;d=p[:,0]-x+curve*dy*dy+.005*noise(p,13,296)
        support=np.exp(-(dy/length)**4)
        ridge=np.exp(-(d/width)**2)*support
        relief+=height*ridge
        lean+=-.25*height*np.tanh(d/width)*ridge
    return relief,lean

def fields(p,seeds,radii):
    # Distort the fracture coordinate system before measuring cell gaps.
    warped=p.copy();warped[:,0]+=.025*np.sin(p[:,1]*17)+.013*noise(p,16,511);warped[:,1]+=.023*np.sin(p[:,0]*13)
    metric=np.array([.78,1.05,1.7]);tree=cKDTree(seeds*metric)
    d,idx=tree.query(warped*metric,k=6,workers=1);power=d-radii[idx];order=np.argsort(power,axis=1);ids=idx[np.arange(len(p)),order[:,0]];dist1=power[np.arange(len(p)),order[:,0]];dist2=power[np.arange(len(p)),order[:,1]]
    gap=dist2-dist1
    rupture=p[:,0]-(.015+.06*np.sin(9*p[:,1])+.018*noise(p,15,343))
    opening=smooth((rupture+.028)/.047)
    # Only a handful of inherited crust rafts survive the rupture. Their
    # rounded irregular contours replace the failed polygon-tile pattern.
    islands=np.zeros(len(p))
    for x,y,wx,wy in [(.10,.075,.061,.044),(.235,-.158,.067,.048),(.415,-.078,.055,.037),(.267,.190,.058,.048)]:
        field=((p[:,0]-x)/wx)**2+((p[:,1]-y)/wy)**2+.19*noise(p,41,722)
        islands=np.maximum(islands,np.exp(-field))
    opening-=islands*1.05
    return opening,ids,rupture,gap

def main(name,step):
    start=time.time();v,f,n,r=core_mesh(step);rng=np.random.default_rng(498)
    # Uneven seed density and a bounded heavy tail create a few broad rafts
    # among many small fragments, rather than equal polygon tiles.
    select=(n[:,2]>.03)&(v[:,2]>-.015);candidates=r[select];chosen=rng.choice(len(candidates),175,replace=False);seeds=candidates[chosen]
    radii=np.minimum(.045,.007*(1+rng.pareto(2.0,len(seeds))))
    opening,ids,rupture,gap=fields(r,seeds,radii)
    upper=smooth((n[:,2]+.2)/.7);opening=np.where(n[:,2]<-.25,-1,opening)
    relief,lean=skin_relief(r)
    mouth=np.exp(-(rupture/.050)**2)*upper
    oldside=1-smooth((rupture+.01)/.025)
    lift=.008+.024*mouth*oldside
    stretched=r.copy();stretched[:,0]*=.32
    detail=np.clip(.00065*noise(stretched,140,783)+.0003*noise(r,325,313),-.001,.002)
    # Shift folds above the molten surface rather than letting troughs
    # puncture it and generate the former orange pinhole artifacts.
    crust_v=v+n*(lift+relief*upper+detail)[:,None]
    crust_v[:,0]+=lean*upper
    sv,sr,sf=clip_vents(crust_v,r,f,opening,.46)
    used,ix=np.unique(sf,return_inverse=True);sv=sv[used];sr=sr[used];sf=ix.reshape(-1,3)
    _,sid,srupt,sgap=fields(sr,seeds,radii)
    fragment=smooth((srupt+.0)/.10)
    # Gently tipped fragments with actual underside thickness. The parent
    # cap stays continuous and curls upward only beside the rupture.
    sv[:,2]+=fragment*.002
    thickness=.003+.006*(1-fragment)+.002*smooth(noise(sr,12,814)+.5)
    crust_temp=980+100*smooth(noise(sr,12,811)+.5)+125*fragment
    sv,sf,sn,sr,st=closed_skin(sv,sf,sr,thickness,crust_temp)
    # Time since emerging from the rupture increases down the exposed
    # stream. The hot source is beneath the lifted cap, not at both tips.
    agegrid=np.geomspace(.01,220,128);temps,residual=film_columns(agegrid)
    age=np.maximum(.012,(r[:,0]-.005)/.19+.05)+.20*smooth(noise(r,24,500)+.3)
    # A continuous film, with older streaks carried down the breakout. The
    # age distribution is authored; only the cooling columns are solved.
    stream=r.copy();stream[:,0]*=.28
    film=smooth(noise(stream,33,847)+.3)**1.4
    fine=smooth(noise(stream,95,516)+.12)**2
    emergence=smooth((r[:,0]-.035)/.19)
    cooling=(120*film+60*fine)*emergence
    # The inflated toe retains a cooler uninterrupted leading surface.
    cooling+=22*smooth((r[:,0]-.53)/.10)
    ct=np.interp(age+cooling,agegrid,temps)
    ct=np.where(n[:,2]<-.12,1000,ct)
    a=dict(v=np.r_[v,sv].astype('f4'),f=np.r_[f,sf+len(v)].astype('i4'),normal=np.r_[n,sn].astype('f4'),rest=np.r_[r,sr].astype('f4'),temperature=np.r_[ct,st].astype('f4'),component=np.r_[np.zeros(len(v),'u1'),np.ones(len(sv),'u1')],camera_eye=np.array([1.30,-1.75,.95]),camera_target=np.array([-.035,.025,.085]),camera_fov=np.array(39.))
    a['uv']=a['rest'][:,:2]*4
    assert all(np.isfinite(a[key]).all() for key in ['v','normal','temperature'])
    path=O/f'{name}.npz';np.savez_compressed(path,**a);preview(a,O/f'{name}-geometry.png')
    report={'device':'CPU','method':'Connected implicit lava volume, authored rupture and local compression, lifted thick crust and differently sized rafts, natural 100-micrometre enthalpy columns','vertices':len(a['v']),'triangles':len(a['f']),'seconds':round(time.time()-start,2),'sourceSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'surfaceTemperatureByAge':dict(zip([str(t) for t in [.02,.1,.5,1,3,10,20]],np.interp([.02,.1,.5,1,3,10,20],agegrid,temps).tolist())),'columnEnergyResidual':float(residual),'limits':['Rupture, fragments and volume morphology are authored, not a new fluid dynamics simulation','Radiative/conductive cooling is one-dimensional and not coupled to crust motion','No animation or inter-fragment collisions have been validated']}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='rupture-01');ap.add_argument('--step',type=float,default=.004);a=ap.parse_args();main(a.name,a.step)
