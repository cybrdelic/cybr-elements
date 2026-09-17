"""CPU cache inspection and surface extraction. No authored cracks or crust."""
from pathlib import Path
import json,argparse,hashlib
import numpy as np
from scipy.ndimage import gaussian_filter,map_coordinates
from skimage.measure import marching_cubes
from PIL import Image,ImageDraw,ImageFont
from lava_mpm import ROOT,Material
from lava_skin import normals
from lava_geometry_preview import raster


def fields(state,spacing,sigma=.7,attribute_sigma=None):
    p=state['x'];dx=np.broadcast_to(np.asarray(spacing),(3,));cell_volume=np.prod(dx)
    padding=np.maximum(3,np.ceil(4*np.broadcast_to(sigma,(3,))))*dx
    lo=np.floor((p.min(0)-padding)/dx)*dx;shape=np.ceil((p.max(0)+padding-lo)/dx).astype(int)+1
    assert np.prod(shape)<6000000
    q=(p-lo)/dx;b=np.floor(q).astype(int);frac=q-b
    names=['temperature','solid','damage'];out={k:np.zeros(shape) for k in ['density']+names}
    for i in (0,1):
        for j in (0,1):
            for k in (0,1):
                ij=b+[i,j,k];w=(frac[:,0] if i else 1-frac[:,0])*(frac[:,1] if j else 1-frac[:,1])*(frac[:,2] if k else 1-frac[:,2])*state['volume']/cell_volume
                np.add.at(out['density'],tuple(ij.T),w)
                for name in names:np.add.at(out[name],tuple(ij.T),w*state[name])
    attribute_sigma=sigma if attribute_sigma is None else attribute_sigma
    attribute_mass=gaussian_filter(out['density'],attribute_sigma)
    out['density']=gaussian_filter(out['density'],sigma)
    for name in names:
        value=gaussian_filter(out[name],attribute_sigma)
        out[name]=np.divide(value,attribute_mass,out=np.zeros(shape),where=attribute_mass>1e-20)
    return lo,dx,out


def reference_coordinates(v,s,dx):
    from scipy.spatial import cKDTree
    distances,near=cKDTree(s['x']).query(v,k=min(8,len(s['x'])))
    if near.ndim==1:near=near[:,None];distances=distances[:,None]
    nearest=near[:,0]
    weights=1/np.maximum(distances,.1*np.min(dx))**4;weights/=weights.sum(1)[:,None]
    inverse_F=np.linalg.inv(s['F'][near])
    mapped=s.get('rest',s['x'])[near]+np.einsum('vkij,vkj->vki',inverse_F,v[:,None,:]-s['x'][near])
    return np.sum(weights[:,:,None]*mapped,axis=1),nearest


def extract(path,method='auto',kernel_destination=None):
    with np.load(path) as saved:
        broken=('bond_broken' in saved and np.any(saved['bond_broken'] & saved['bond_frozen'][saved['bond_edges']].all(1)))
        coherent='bond_frozen' in saved and saved['bond_frozen'].any()
    # Crystallization changes constitutive behavior, not the physical free
    # boundary into a stack of quadrature cubes. Keep volume-constrained
    # density surfacing until a crack actually needs separated topology.
    if method=='auto' and broken:
        from lava_mpm_gap_surface import extract as gap_extract
        return gap_extract(path)
    if method=='material':
        from lava_mpm_material_surface import extract as material_extract
        return material_extract(path,smooth_outer=method=='auto')
    s=dict(np.load(path));folder=path.parent;meta=json.loads((folder/'state.json').read_text());sample=np.array(meta.get('sample_size',[meta['spacing']]*3));dx=sample*.35
    # A flat simulation cell does not imply a flat physical surface kernel.
    # Use a physical isotropic reconstruction radius on stretched grids;
    # otherwise each particle layer becomes a separate horizontal terrace.
    # Heat/phase retain their finer vertical sampling instead of being mixed
    # through the entire geometric filter width.
    sigma=np.full(3,float(sample.max()*.5))/dx
    lo,dx,field=fields(s,dx,sigma,np.full(3,1.4));density=field['density'];target=float(s['volume'].sum());left=.02;right=density.max()*.95
    for _ in range(12):
        level=(left+right)/2;v,f,_,_=marching_cubes(density,level,spacing=tuple(dx));v+=lo
        volume=float(np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))/6)
        if volume<0:f=f[:,[0,2,1]];volume=-volume
        if volume>target:left=level
        else:right=level
    temp=map_coordinates(field['temperature'],((v-lo)/dx).T,order=1,mode='nearest')
    solid=map_coordinates(field['solid'],((v-lo)/dx).T,order=1,mode='nearest')
    damage=map_coordinates(field['damage'],((v-lo)/dx).T,order=1,mode='nearest')
    center=(s['x'].min(0)+s['x'].max(0))*.5;size=float(np.max(np.ptp(s['x'],axis=0)))
    eye=center+np.array([.8,-1.5,1.15])*size
    out=path.with_name(path.stem+'-surface.npz') if kernel_destination is None else Path(kernel_destination)
    # Phase is continuous; material identity is categorical. Rest positions
    # belong to the source particles, not this frame's deformed mesh.
    material_rest,nearest=reference_coordinates(v,s,dx)
    components=s.get('labels',np.zeros(len(s['x']),dtype=int))[nearest].astype(int)
    np.savez_compressed(out,v=v,f=f,normal=normals(v,f),uv=material_rest[:,:2],rest=material_rest,temperature=temp,solid=solid,damage=damage,component=components,
                        camera_eye=eye,camera_target=center,camera_fov=38.,time=s['time'])
    receipt=dict(source=str(path),sourceSha256=hashlib.sha256(path.read_bytes()).hexdigest(),physicalSeconds=float(s['time']),vertices=len(v),triangles=len(f),
                 solverParticleVolumeM3=target,reconstructedVolumeM3=volume,relativeVolumeDifference=abs(volume-target)/target,kernelSigmaRenderCells=sigma.tolist(),kernelSigmaM=(sigma*dx).tolist(),renderCellSizeM=dx.tolist(),
                 method='density reconstruction',fractureTopologyPreserved=not bool(broken),
                 limits='Unfractured material reconstruction. Solidification does not switch the exterior to voxel cells. Explicit --method kernel on a fractured state does not preserve fracture topology. Material coordinates use local inverse deformation gradients.')
    out.with_suffix('.json').write_text(json.dumps(receipt,indent=2))
    return out


def image_surface(path,camera=None):
    a=np.load(path);v=a['v'];f=a['f'];view=a if camera is None else camera;eye=view['camera_eye'];center=view['camera_target'];forward=center-eye;forward/=np.linalg.norm(forward)
    right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward)
    w=720;h=405;fl=w/(2*np.tan(np.deg2rad(38)/2))
    projected=(v-center)@np.array([right,up,forward]).T
    distance=max(np.max(abs(projected[:,0])*fl/(w*.43)-projected[:,2]),np.max(abs(projected[:,1])*fl/(h*.42)-projected[:,2]))
    eye=center-forward*distance
    q=(v-eye)@np.array([right,up,forward]).T
    p=np.c_[w/2+fl*q[:,0]/q[:,2],h/2-fl*q[:,1]/q[:,2],q[:,2]]
    n=a['normal'][f].mean(1);shade=.15+.85*np.maximum(0,n@np.array([-.4,-.4,.8246]))
    t=a['temperature'][f].mean(1);solid=a['solid'][f].mean(1);damage=a['damage'][f].mean(1)
    heat=np.clip((t-900)/550,0,1);thermal=np.c_[heat,heat**3*.65,heat**8*.1]
    phase=np.c_[1-solid,.22+.45*solid,solid*.75]*shade[:,None]
    stress=np.c_[.15+.85*damage,.15*(1-damage),.18*(1-damage)]*shade[:,None]
    gray=np.tile([.42,.44,.47],(len(f),1))*shade[:,None]
    canvas=Image.new('RGB',(1440,900));draw=ImageDraw.Draw(canvas)
    for i,(title,color) in enumerate([('Temperature / solved enthalpy',thermal),('Solid fraction / phase law',phase),('Surface geometry / CPU diagnostic',gray),('Tensile damage / persistent material state',stress)]):
        pixels=raster(p,f,(np.clip(color,0,1)**(1/2.2)*255).astype('u1'),w,h)
        x=(i%2)*720;y=(i//2)*450;canvas.paste(Image.fromarray(pixels),(x,y+30));draw.text((x+20,y+8),title,fill='#b8b8b8')
    draw.text((20,875),f'Physical time {float(a["time"]):.3f} s | Temperature {t.min():.0f}-{t.max():.0f} K | Diagnostic colors, not a beauty render',fill='#aaa')
    out=path.with_name(path.stem+'-diagnostic.png');canvas.save(out)
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--frame',default='state');p.add_argument('--method',choices=['auto','material','kernel'],default='auto');a=p.parse_args()
    path=ROOT/a.name/(a.frame+'.npz');surface=extract(path,a.method);image=image_surface(surface)
    print(json.dumps(dict(surface=str(surface),diagnostic=str(image),device='CPU',size=[1440,900])))
