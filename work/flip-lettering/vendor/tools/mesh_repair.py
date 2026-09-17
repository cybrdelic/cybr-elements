"""Detail-preserving reconstruction for CYBR FLIP III.1.

Default: II-scale PCA support, no temporal field blend, no geometric volume
inflation. Sparse primary markers are removed BEFORE splatting the body, and
rendered as volume-carrying droplets. New meshes are derived from new solver
states. The --profile switch enables a controlled old/new mesher ablation on
identical primary states; it never changes the underlying simulation.
"""
from __future__ import annotations
from pathlib import Path
import os
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'NUMBA_NUM_THREADS'):
    os.environ.setdefault(name, '1')
import argparse, gzip, hashlib, json, time
import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree
from skimage.measure import marching_cubes
from mesh_cache import deposit, sample, smooth_mesh
from mesh_ii import splat_anisotropic, signed_volume, DiffuseWhitewater, caustics, reconstruct as reconstruct_ii
from mesh_iii import Reconstruction as PreviousReconstruction, normals_area, encode
ROOT = Path(__file__).resolve().parents[1]

class DetailReconstruction(PreviousReconstruction):
    def __init__(self, config):
        super().__init__(config)
        self.options = config.get('surfaceOptions', {})
        self.spacing = self.h * self.options.get('spacingFactor', .43)
        self.grid_shape = tuple(np.ceil(self.extent / self.spacing).astype(int) + 1)
        self.coords = np.indices(self.grid_shape, dtype=np.float32)
        self.previous_iso = 1.8

    def reconstruct(self, p, v, history, obstacles, dt):
        h, spacing, shape = self.h, self.spacing, self.grid_shape
        rho, vx, vy, vz = deposit(p, v, shape, spacing, h*.98)
        density = sample(rho, p, spacing)
        boundary = np.flatnonzero(density < 3.55)
        radius = h*self.options.get('kernelRadiusFactor', .99)
        G = np.zeros((len(p), 6), np.float32); G[:, :3] = 1/radius**2
        bounds = np.full((len(p), 3), radius, np.float32)
        centers = p.copy()
        if len(self.isolated) < len(p):
            self.isolated = np.pad(self.isolated, (0,len(p)-len(self.isolated)))
        # Classifier state is recomputed for every particle, so an isolated
        # marker cannot remain a droplet after rejoining the bulk liquid.
        isolated = np.zeros(len(p), bool)
        axis_ratio_max = 1.
        if len(boundary):
            tree = cKDTree(p)
            for begin in range(0, len(boundary), 16000):
                ids = boundary[begin:begin+16000]
                dist, nb = tree.query(p[ids], k=min(32, len(p)), workers=1)
                if dist.ndim == 1:
                    dist, nb = dist[:, None], nb[:, None]
                valid = dist < h*1.7
                # Hysteresis only changes phase near the sparse/bulk threshold;
                # positions and radii are never interpolated between states.
                neighbours = (dist < h*1.0).sum(axis=1)
                was = self.isolated[ids]
                isolated[ids] = np.where(was, (density[ids]<1.40)&(neighbours<7),
                                             (density[ids]<1.16)&(neighbours<5))
                weight = np.maximum(0, 1-(dist/(h*1.7))**3)*valid
                total = np.maximum(weight.sum(axis=1), 1e-8)
                points = p[nb]
                mean = np.einsum('nk,nkj->nj', weight, points)/total[:, None]
                delta = points-mean[:, None,:]
                cov = np.einsum('nk,nki,nkj->nij',weight,delta,delta)/total[:,None,None]
                eig, Q = np.linalg.eigh(cov)
                std = np.sqrt(np.maximum(eig,(h*.1)**2))
                std = np.maximum(std, std[:,-1,None]/2.7)
                axes = std/np.maximum(np.prod(std,axis=1)**(1/3),1e-8)[:,None]
                unreliable = valid.sum(axis=1)<10
                axes[unreliable] = 1
                axis_ratio_max=max(axis_ratio_max,float((axes[:,-1]/axes[:,0]).max()))
                inv=1/(radius*axes)**2
                matrix=np.einsum('nik,nk,njk->nij',Q,inv,Q)
                G[ids]=matrix[:,[0,1,2,0,0,1],[0,1,2,1,2,2]]
                bounds[ids]=np.sqrt(np.einsum('nik,nk->ni',Q*Q,(radius*axes)**2))
                blend=np.where(unreliable,0.,.12)[:,None]
                centers[ids]=p[ids]*(1-blend)+mean*blend
        self.isolated=isolated
        main=~isolated
        field=splat_anisotropic(centers[main],G[main],bounds[main],shape,spacing)
        field=gaussian_filter(field,self.options.get('fieldSigma',.34),mode='constant').astype(np.float32)
        # Explicit clipping against the real solid, not an expanded silhouette.
        x,y,z=self.coords*spacing
        solid=(x<h*.98)|(x>self.extent[0]-h*.98)|(y<h*.98)|(y>self.extent[1]-h*.98)|(z<h*.98)|(z>self.extent[2]-h*.98)
        for o in obstacles:
            c=o['center']
            if o['kind']=='sphere':
                solid |= (x-c[0])**2+(y-c[1])**2+(z-c[2])**2<o['radius']**2
            elif o['kind']=='box':
                solid |= (abs(x-c[0])<o['half'][0])&(abs(y-c[1])<o['half'][1])&(abs(z-c[2])<o['half'][2])
        field[solid]=0
        # The baseline implementation could splat a marker into the body and
        # also render it as a droplet. These representation sets are disjoint.
        drops,radii,drop_v,counts=self.droplet_clusters(p[isolated],v[isolated])
        target=max(int(main.sum())*(h*.5)**3,1e-12)
        lo=.12;hi=min(3.3,float(field.max())*.96)
        if not hi>lo:raise RuntimeError('Liquid field has insufficient support')
        iso=float(np.clip(self.previous_iso,lo,hi));best=None;root=[];lo_error=hi_error=None
        for iteration in range(10):
            verts,faces,_,_=marching_cubes(field,level=iso,spacing=(spacing,)*3,gradient_direction='ascent',allow_degenerate=False)
            verts=verts.astype(np.float32);faces=faces.astype(np.int32)
            volume=abs(signed_volume(verts,faces));error=(volume-target)/target
            root.append({'iso':iso,'relativeError':error})
            if best is None or abs(error)<best[0]:best=(abs(error),verts,faces,iso)
            if abs(error)<.0015:break
            if error>0:lo=iso;lo_error=volume-target
            else:hi=iso;hi_error=volume-target
            derivative=-np.count_nonzero(abs(field-iso)<.13)*spacing**3/.26
            candidate=iso-(volume-target)/min(derivative,-1e-12)
            if lo_error is not None and hi_error is not None:
                candidate=(lo*hi_error-hi*lo_error)/(hi_error-lo_error)
            iso=float(candidate if lo+1e-5<candidate<hi-1e-5 else .5*(lo+hi))
        _,verts,faces,iso=best;self.previous_iso=iso
        verts,_=smooth_mesh(verts,faces,int(self.options.get('meshSmoothingPasses',2)))
        if signed_volume(verts,faces)<0:faces=faces[:,[0,2,1]]
        normals,area=normals_area(verts,faces)
        # Unit geometric normals keep actual high-frequency shape information.
        # No normal-driven dilation or root-recovery SDF is applied afterward.
        volume=abs(signed_volume(verts,faces))
        encoded=np.rint(np.clip(verts/self.extent,0,1)*65535).astype(np.uint16).astype(np.float32)*self.extent/65535
        encoded_volume=abs(signed_volume(encoded,faces))
        nominal=len(p)*(h*.5)**3;drop_volume=float(counts.sum())*(h*.5)**3
        stats={'kernel':'detail PCA; II-sized support; disjoint volume-carrying droplets',
            'volumeRecovery':None,'normalVolumeCorrectionDistance':0.,'temporalFieldBlend':0.,'shapeHistoryWeight':0.,
            'kernelRadiusFactor':radius/h,'fieldSigma':self.options.get('fieldSigma',.34),
            'meshSmoothingPasses':int(self.options.get('meshSmoothingPasses',2)),
            'maximumAxisRatio':axis_ratio_max,'anisotropicParticles':len(boundary),
            'targetMeshVolume':target,'signedMeshVolume':volume,'encodedMeshVolume':encoded_volume,
            'meshVolumeRelativeError':(volume-target)/target,'encodedVolumeRelativeError':(encoded_volume-target)/target,
            'nominalParticleVolume':nominal,'primaryDropletVolume':drop_volume,
            'dropletPrimaryMarkers':int(isolated.sum()),'dropletClusters':len(drops),'meshedPrimaryMarkers':int(main.sum()),
            'primaryRepresentationSetsDisjoint':True,'totalRepresentedVolumeError':(volume+drop_volume-nominal)/nominal,
            'normalMaximumLengthError':float(abs(np.linalg.norm(normals,axis=1)-1).max()),
            'rootIterations':len(root),'volumeRoot':root,'isovalue':iso,'surfaceArea':area,
            'globalVolumeRootConverged':best[0]<.003,'localMassConservationClaim':False}
        self.frame+=1
        return field,(vx,vy,vz),verts,normals,faces,drops,radii,drop_v,iso,stats

class BaselineReconstruction(DetailReconstruction):
    """Exact II reconstruction for isolated mesher comparison; not delivery default."""
    def reconstruct(self,p,v,history,obstacles,dt):
        f,vel,vv,nn,ff,drops,iso,s=reconstruct_ii(p,v,self.h,self.spacing,self.grid_shape,self.extent,self.previous_iso)
        self.previous_iso=iso
        rr=np.full(len(drops),self.h*np.cbrt(3/(32*np.pi)),np.float32)
        s['volumeRecovery']=None;s['primaryRepresentationSetsDisjoint']=False;s['localMassConservationClaim']=False
        return f,vel,vv,nn,ff,drops,rr,np.zeros_like(drops),iso,s

def mesh_scene(name, profile='repair', limit=None, start=0, streaming=False, out_suffix=''):
    folder=ROOT/'cache'/name
    while not (folder/'manifest.json').exists():
        if not streaming:raise FileNotFoundError(folder/'manifest.json')
        time.sleep(1)
    manifest=json.loads((folder/'manifest.json').read_text());config=manifest['config']
    reconstruction_config = dict(config)
    if profile != 'repair':
        # A fresh public repair cache carries surfaceOptions. Do not let those
        # options silently disable history in the deliberately historical III
        # comparison or alter the original II sampling resolution.
        reconstruction_config.pop('surfaceOptions', None)
        if profile == 'ii':
            reconstruction_config['surfaceOptions'] = {'spacingFactor': .45}
    rec=({'repair':DetailReconstruction,'ii':BaselineReconstruction,'iii':PreviousReconstruction}[profile])(reconstruction_config)
    ww=DiffuseWhitewater(config['seed']+501)
    stats=[];started=time.time();f=start
    out=folder if not out_suffix else ROOT/'cache'/(name+out_suffix)
    out.mkdir(parents=True,exist_ok=True)
    while True:
        current=json.loads((folder/'manifest.json').read_text())
        total=limit if limit is not None else len(current['frames'])
        if f>=total:break
        if f>=len(current['frames']):
            if current.get('simulationComplete'):break
            if not streaming:break
            time.sleep(1);continue
        info=current['frames'][f];n=info['particles']
        raw=np.fromfile(folder/f'{f:04d}.particles',dtype='<f4')
        if raw.size!=n*6:raise ValueError('Primary cache length mismatch')
        p=raw[:n*3].reshape(-1,3);v=raw[n*3:].reshape(-1,3)
        history=np.fromfile(folder/f'{f:04d}.shape',dtype='<f4').reshape(n,6)
        obstacles=info.get('colliders',config['obstacles'])
        field,vel,verts,normals,faces,drops,radii,dv,iso,measure=rec.reconstruct(p,v,history,obstacles,manifest['frameDt'])
        if not np.isfinite(verts).all() or not np.isfinite(normals).all():raise RuntimeError('Nonfinite surface')
        ww_field=np.exp(np.clip(field/(rec.h*.5),-8,8)).astype(np.float32) if measure.get('volumeRecovery') else field
        ww_iso=1. if measure.get('volumeRecovery') else iso
        white=ww.step(p,v,ww_field,vel,rec.spacing,rec.h,manifest['frameDt'],ww_iso,rec.extent,obstacles,manifest.get('preset',name) not in ['viscous','capillary'])
        foam=np.zeros(len(verts),np.float32)
        if len(white):
            fp=white[white[:,4]==0]
            if len(fp):
                dist,ids=cKDTree(fp[:,:3]).query(verts,k=min(8,len(fp)),workers=1)
                if dist.ndim==1:dist=dist[:,None];ids=ids[:,None]
                kernel=np.maximum(0,1-dist/(rec.h*.92))**3
                foam=1-np.exp(-np.sum(kernel*fp[ids,5],axis=1)*.65)
        diagnostic=p[np.linspace(0,len(p)-1,min(26000,len(p))).astype(int)]
        caustic,photon_stats=caustics(verts,normals,faces,field,iso,rec.extent,rec.h)
        path=out/f'{f:04d}.mesh.gz'
        digest=encode(path,verts,normals,faces,drops,radii,white,diagnostic,rec.extent,foam,caustic)
        entry={'frame':f,'vertices':len(verts),'triangles':len(faces),'primaryDroplets':len(drops),
            'secondaryParticles':len(white),'foam':int(np.sum(white[:,4]==0)),'spray':int(np.sum(white[:,4]==1)),
            'bubbles':int(np.sum(white[:,4]==2)),'bytes':path.stat().st_size,'payloadSha256':digest,
            'sourcePrimarySha256':info['primarySha256'],'caustics':photon_stats,**measure}
        stats.append(entry)
        # Separate progress output avoids concurrent modification of a simulation manifest.
        (out/f'mesh-{profile}-progress.json').write_text(json.dumps({'profile':profile,'lastFrame':f,'meshes':stats}))
        if f%8==0:print(json.dumps({'scene':name,'profile':profile,'frame':f,'triangles':len(faces),'relativeVolumeError':measure['meshVolumeRelativeError'],'droplets':len(drops),'whitewater':len(white),'elapsed':round(time.time()-started,1)}),flush=True)
        f+=1
    manifest=json.loads((folder/'manifest.json').read_text())
    manifest['meshes']=stats
    manifest['surface']={'profile':profile,'method':stats[0]['kernel'] if stats else profile,'spacing':rec.spacing,
        'noGeometricVolumeInflation':profile!='iii','localMassConservationClaim':False}
    manifest['whitewater']={'twoWayCoupling':False,'births':ww.total_births,'deaths':ww.total_deaths,'transitions':ww.transitions}
    manifest['meshWallSeconds']=time.time()-started
    manifest['meshingComplete']=True
    if out!=folder:
        manifest['name']=out.name
        manifest['frames']=manifest['frames'][:limit] if limit else manifest['frames']
    # Wait for simulation completion before replacing its primary manifest.
    if out==folder and not manifest.get('simulationComplete'):
        while True:
            latest=json.loads((folder/'manifest.json').read_text())
            if latest.get('simulationComplete'):
                latest.update({k:manifest[k] for k in ['meshes','surface','whitewater','meshWallSeconds']});manifest=latest;break
            time.sleep(1)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('MESH COMPLETE',name,profile,time.time()-started,flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('name');a.add_argument('--profile',choices=['repair','ii','iii'],default='repair')
    a.add_argument('--limit',type=int);a.add_argument('--start',type=int,default=0);a.add_argument('--stream',action='store_true');a.add_argument('--suffix',default='')
    o=a.parse_args();mesh_scene(o.name,o.profile,o.limit,o.start,o.stream,o.suffix)
