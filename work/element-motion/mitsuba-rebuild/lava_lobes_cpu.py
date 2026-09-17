"""Reference-led pahoehoe geometry study, generated entirely on the CPU.

The lobe layout and compressed folds are authored geometry, not a claim of a
new fluid solver. A separate molten body, closed millimetre-thick crust and
enthalpy-column cooling make the material/occlusion test reproducible.
"""
from pathlib import Path
import os, json, time, argparse, hashlib
os.environ.update(CUDA_VISIBLE_DEVICES='-1', OPENBLAS_NUM_THREADS='1', NUMBA_NUM_THREADS='2')
import numpy as np
from scipy.ndimage import map_coordinates, distance_transform_edt
from scipy.special import erf
from lava_skin import normals
from lava_cohesive_cpu import clip_vents
from lava_thermal import columns
from lava_geometry_preview import raster
from PIL import Image

R=Path(__file__).resolve().parent/'lava-focus'
O=R/'lobes'; O.mkdir(exist_ok=True)

def smooth(x):
    x=np.clip(x,0,1); return x*x*(3-2*x)

def noise(p, freq, seed):
    field=np.random.default_rng(seed).normal(size=(40,40,40)).astype('f4')
    return map_coordinates(field,(p*freq+13).T,order=3,mode='wrap')

def boundary(f):
    e=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]])
    _,inv,count=np.unique(np.sort(e,axis=1),axis=0,return_inverse=True,return_counts=True)
    return e[count[inv]==1]

def closed_skin(v, f, rest, thickness, temp):
    n=normals(v,f); b=boundary(f); count=len(v)
    lower=v-n*thickness[:,None]
    side=np.concatenate([np.c_[b[:,0],b[:,0]+count,b[:,1]+count],np.c_[b[:,0],b[:,1]+count,b[:,1]]])
    allv=np.r_[v,lower]; allf=np.r_[f,f[:,[0,2,1]]+count,side]
    return allv,allf,normals(allv,allf),np.r_[rest,rest],np.r_[temp,np.minimum(1270,temp+200)]

def make_lobe(start,end,width,height,seed,folds,hot_tip,nu=380,nv=192):
    u=np.linspace(.0002,.9998,nu); theta=np.linspace(-np.pi,np.pi,nv,endpoint=False)
    U,Q=np.meshgrid(u,theta,indexing='ij'); t=U.ravel(); q=Q.ravel()
    start=np.asarray(start); end=np.asarray(end); axis=end-start; length=np.linalg.norm(axis[:2]); direction=axis[:2]/length; side=np.array([-direction[1],direction[0]])
    # Broad rounded noses; no vertical cut perimeter or shallow plate base.
    profile=np.maximum(0,1-(2*t-1)**4)**.5
    widthfield=width*(.92+.07*np.sin(9*t+seed))
    center=start[None,:]+t[:,None]*axis[None,:]
    center[:,:2]+=side[None,:]*(.028*np.sin(np.pi*t)*np.sin(5*t+seed))[:,None]
    rest=np.c_[t*length,q*width,np.full(len(t),seed*.2)]
    upper=np.maximum(0,np.sin(q)); skin_top=smooth((np.sin(q)+.12)/.7)
    # Arcs bend downstream at the centre of the lobe. Two wavelengths and
    # slow phase drift prevent identical evenly spaced rings.
    phase=2*np.pi*(folds*(t+.018*np.sin(10*t+seed)) - 1.35*np.sin(q) + .28*np.sin(3*q+9*t)+.42*noise(rest,5,seed+1))
    bunch=smooth(noise(rest,7,seed+3)+.35)
    amp=(.002+.011*bunch)*smooth(t/.16)*smooth((1-t)/.12)*skin_top
    fold=(.85*np.cos(phase)+.15*np.cos(2*phase-.65))
    v=center.copy(); v[:,:2]+=side[None,:]*(widthfield*profile*np.cos(q))[:,None]
    v[:,2]+=height*profile*np.where(np.sin(q)>0,np.sin(q),.25*np.sin(q))
    v[:,2]+=amp*fold+.008*noise(rest,13,seed+109)*skin_top*smooth(profile/.3)
    # Nested small compressional wrinkles ride the broad deformations.
    fine_phase=2.35*phase+2.7*noise(rest,13,seed+244)
    v[:,2]+=.0024*np.cos(fine_phase)*skin_top*smooth(profile/.35)
    # Forward leaning fold crests give occluding lips instead of bump-only
    # grooves. The coarse form can be judged with microdetail disabled.
    v[:,:2]+=direction[None,:]*(-.34*amp*np.sin(phase-.45))[:,None]
    j=np.arange(nu-1)[:,None]*nv+np.arange(nv)[None,:]; k=np.arange(nu-1)[:,None]*nv+(np.arange(nv)+1)[None,:]%nv
    f=np.r_[np.c_[j.ravel(),(j+nv).ravel(),(k+nv).ravel()],np.c_[j.ravel(),(k+nv).ravel(),k.ravel()]].astype('i4')
    # Correct outward winding explicitly from the radial cross-section.
    if np.mean(normals(v,f)[:,2]*np.sin(q))<0:f=f[:,[0,2,1]]
    n=normals(v,f)
    # Longitudinally dragged striations plus fine broken vesicular relief.
    stretched=rest.copy(); stretched[:,0]*=.22
    micro=(.0015*noise(stretched,105,seed+23)+.0010*noise(v,210,seed+42)+.00040*noise(v,420,seed+92))*smooth(profile/.25)
    top=v+n*(.006+micro)[:,None]
    # Sparse folds open; the front lip has one broad molten breakout.
    wrap=np.arctan2(np.sin(phase-2.7),np.cos(phase-2.7))
    gate=smooth((noise(rest,6,seed+17)-.24)/.48)*skin_top
    vents=np.exp(-(wrap/.48)**2)*gate*.98
    tip_start=.82+.045*noise(v,14,seed+31)
    cooling_skin=.24+.90*smooth(noise(v,44,seed+74)+.38)
    tip=smooth((t-tip_start)/.04)*smooth((np.sin(q)+.15)/.5)*hot_tip*cooling_skin
    # A few irregular shorter ruptures, along the flow tension direction.
    tear=np.exp(-((np.cos(q)-.23-.13*np.sin(t*15+seed))/.048)**2)*smooth((t-.48)/.1)*smooth((.86-t)/.06)*skin_top*.42
    opening=np.maximum.reduce([vents,tip,tear])
    sv,sr,sf=clip_vents(top,rest,f,opening,.46)
    used,ix=np.unique(sf,return_inverse=True); sv=sv[used]; sr=sr[used]; sf=ix.reshape(-1,3)
    thick=.003+.0015*smooth(noise(sr,24,seed+4)+.5)
    crust_temp=970+95*smooth(noise(sr,9,seed+6)+.5)+190*smooth((sr[:,0]/length-.81)/.18)
    sv,sf,sn,sr,st=closed_skin(sv,sf,sr,thick,crust_temp)
    # Core folds retain volume underneath each opening. Cool the exposed
    # skin by its age; recently exposed noses retain the hottest material.
    ages=.08+9.0*smooth((1-t)/.6)+3*smooth(noise(rest,22,seed+90)+.3)
    ages=np.maximum(.03,ages-2.5*smooth((t-.86)/.1))
    grid=np.geomspace(.02,18,128); lut,residual=columns(grid,np.full(len(grid),1450.))
    ct=np.interp(ages,grid,lut)
    # Contact-cooled bands beneath closed crust make heat recede into
    # fissures; radiation is temperature driven, not a painted RGB map.
    exposed=opening.reshape(nu,nv)>.46
    distance=distance_transform_edt(exposed,sampling=[length/(nu-1),2*np.pi*width/nv]).ravel()
    # Approximate lateral diffusion from the cold crust banks. Keep this
    # separate from the column energy audit: it is not a coupled 3D solve.
    edge_temperature=1125+(ct-1125)*erf(distance/(2*np.sqrt(5e-7*np.maximum(ages,.4))))
    ct=np.where(exposed.ravel(),edge_temperature,np.minimum(ct,1210.))
    ct=np.where(np.sin(q)<-.05,990,ct)
    cv=v-n*.001
    # Close both ends with small caps hidden inside the rounded lobe poles.
    capv=np.r_[cv,cv[:nv].mean(0)[None,:],cv[-nv:].mean(0)[None,:]]
    cf=np.r_[f,np.c_[np.full(nv,len(cv)),np.arange(nv),np.roll(np.arange(nv),1)],np.c_[np.full(nv,len(cv)+1),len(cv)-nv+np.roll(np.arange(nv),1),len(cv)-nv+np.arange(nv)]]
    cr=np.r_[rest,rest[:nv].mean(0)[None,:],rest[-nv:].mean(0)[None,:]]
    ct=np.r_[ct,990,990]
    return [(capv,cf,normals(capv,cf),cr,ct,0),(sv,sf,sn,sr,st,1)],residual

def preview(a,path,width=800):
    v,f,n,temp=a['v'],a['f'],a['normal'],a['temperature']; eye=a['camera_eye']; target=a['camera_target']; forward=target-eye; forward/=np.linalg.norm(forward); right=np.cross(forward,[0,0,1]); right/=np.linalg.norm(right); up=np.cross(right,forward)
    q=(v-eye)@np.array([right,up,forward]).T; height=round(width*.7); fl=width/(2*np.tan(np.deg2rad(float(a['camera_fov']))/2)); p=np.c_[width/2+fl*q[:,0]/q[:,2],height/2-fl*q[:,1]/q[:,2],q[:,2]]
    light=np.array([-.45,-.2,.87]); shade=.10+.90*np.maximum(0,n[f].mean(1)@light); heat=smooth((temp[f].mean(1)-1100)/280)
    cool=np.array([.32,.33,.34])[None,:]*shade[:,None]; hot=np.c_[.6+.4*heat,.03+.38*heat,np.full(len(f),.004)]
    col=cool*(1-heat[:,None])+hot*heat[:,None]
    im=raster(p,f,(np.clip(col,0,1)**(1/2.2)*255).astype('u1'),width,height); Image.fromarray(im).save(path)

def main(name,detail):
    start=time.time(); combined=[]; residuals=[]
    # One leading tongue, an older rear inflation lobe, and a side breakout.
    specs=[([-.85,.18,.047],[.15,.29,.048],.34,.205,81,21,.40),
           ([-.65,-.06,.055],[.27,-.35,.055],.225,.145,143,23,.95),
           ([-.65,.12,.092],[.94,.06,.067],.235,.155,229,32,1.)]
    for spec in specs:
        pieces,residual=make_lobe(*spec,nu=detail,nv=160);combined.extend(pieces);residuals.append(residual)
    vertices=[];faces=[];nn=[];rr=[];tt=[];cc=[];offset=0
    for v,f,n,r,t,c in combined:
        vertices.append(v);faces.append(f+offset);nn.append(n);rr.append(r);tt.append(t);cc.append(np.full(len(v),c,'u1'));offset+=len(v)
    a=dict(v=np.concatenate(vertices).astype('f4'),f=np.concatenate(faces).astype('i4'),normal=np.concatenate(nn).astype('f4'),rest=np.concatenate(rr).astype('f4'),temperature=np.concatenate(tt).astype('f4'),component=np.concatenate(cc),camera_eye=np.array([1.25,-2.60,1.55]),camera_target=np.array([-.04,.02,.13]),camera_fov=np.array(37.))
    a['uv']=a['rest'][:,:2]*4
    assert all(np.isfinite(a[k]).all() for k in ['v','normal','temperature'])
    assert a['f'].min()>=0 and a['f'].max()<len(a['v'])
    path=O/f'{name}.npz';np.savez_compressed(path,**a)
    preview(a,O/f'{name}-geometry.png')
    report={'device':'CPU','seconds':round(time.time()-start,2),'vertices':len(a['v']),'triangles':len(a['f']),'bounds':np.array([a['v'].min(0),a['v'].max(0)]).tolist(),'maxThermalEnergyResidual':max(residuals),'meshSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'method':'Authored three-dimensional inflation lobes and compressed ropy folds, separate closed basalt crust with contour-clipped apertures, 1D enthalpy cooling and thermal emission','limits':['Geometry is a reference-led procedural material study, not a new validated flow simulation','Lobe intersections are overlapping opaque volumes; no two-way mechanics or motion has been validated'],'reference':'https://www.nps.gov/articles/000/lava-flow-forms.htm'}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='lobes-01');ap.add_argument('--detail',type=int,default=360);a=ap.parse_args();main(a.name,a.detail)
