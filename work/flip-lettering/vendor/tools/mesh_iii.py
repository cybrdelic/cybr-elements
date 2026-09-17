"""CYBR FLIP III: transported anisotropic liquid surfaces from NEW solver states.

Particle IDs are their stable cache indices (these scenes have sources, no sinks).
The primary liquid body and volume-carrying droplet clusters are disjoint sets.
Local PCA is blended with the transported SPD shape tensor, then a semi-Lagrangian
scalar-history correction reduces temporal resampling noise. This is still an
implicit reconstruction, not arbitrary-thickness explicit surface tracking.
"""
from pathlib import Path
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import sys,json,time,gzip,struct,hashlib
import numpy as np
from scipy.ndimage import gaussian_filter,map_coordinates,distance_transform_edt
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from skimage.measure import marching_cubes
from numba import njit
from mesh_ii import splat_anisotropic,signed_volume,DiffuseWhitewater,caustics
from mesh_cache import deposit,smooth_mesh,sample
ROOT=Path(__file__).resolve().parents[1]

@njit(cache=True)
def normals_area(verts,faces):
    normals=np.zeros_like(verts)
    area=0.
    for a,b,c in faces:
        ab=verts[b]-verts[a];ac=verts[c]-verts[a]
        normal=np.cross(ab,ac)
        area+=.5*np.sqrt(np.sum(normal*normal))
        normals[a]+=normal;normals[b]+=normal;normals[c]+=normal
    for i in range(len(normals)):
        length=np.sqrt(np.sum(normals[i]*normals[i]))
        if length>1e-15:normals[i]/=length
        else:normals[i,1]=1
    return normals,area

@njit(cache=True)
def clip_geometry(verts,extent,h):
    for n in range(len(verts)):
        for c in range(3):
            verts[n,c]=max(h*.98,min(extent[c]-h*.98,verts[n,c]))
    return verts

class Reconstruction:
    def __init__(self,config):
        self.config=config;self.h=config['h'];self.spacing=self.h*config.get('surfaceOptions',{}).get('spacingFactor',.43)
        self.extent=np.array(config['extent'],np.float32)
        self.grid_shape=tuple(np.ceil(self.extent/self.spacing).astype(int)+1)
        self.previous_field=None;self.previous_iso=1.8;self.isolated=np.empty(0,bool)
        self.coords=np.indices(self.grid_shape,dtype=np.float32)
        self.frame=0
    def droplet_clusters(self,p,v):
        if not len(p):return p,np.empty(0,np.float32),v,np.empty(0,np.int32)
        pairs=cKDTree(p).query_pairs(self.h*.62,output_type='ndarray')
        if len(pairs):
            a=np.concatenate([pairs[:,0],pairs[:,1]]);b=np.concatenate([pairs[:,1],pairs[:,0]])
            graph=coo_matrix((np.ones(len(a)),(a,b)),shape=(len(p),len(p)))
            count,labels=connected_components(graph,directed=False)
        else:count=len(p);labels=np.arange(len(p))
        counts=np.bincount(labels,minlength=count)
        centers=np.column_stack([np.bincount(labels,weights=p[:,c],minlength=count)/counts for c in range(3)]).astype(np.float32)
        speed=np.column_stack([np.bincount(labels,weights=v[:,c],minlength=count)/counts for c in range(3)]).astype(np.float32)
        radius=(counts*(self.h*.5)**3*3/(4*np.pi))**(1/3)
        return centers,radius.astype(np.float32),speed,counts
    def reconstruct(self,p,v,history,obstacles,dt):
        h=self.h;spacing=self.spacing;shape=self.grid_shape;extent=self.extent
        rho,vx,vy,vz=deposit(p,v,shape,spacing,h*1.03)
        tree=cKDTree(p)
        density=sample(rho,p,spacing)
        boundary=np.flatnonzero(density<4.8)
        radius=h*1.13
        G=np.zeros((len(p),6),np.float32);G[:,:3]=1/radius**2
        bounds=np.full((len(p),3),radius,np.float32);centers=p.copy()
        if len(self.isolated)<len(p):self.isolated=np.pad(self.isolated,(0,len(p)-len(self.isolated)))
        min_eigen=1.;maximum_axis_ratio=1.;history_particles=0
        for start in range(0,len(boundary),20000):
            ids=boundary[start:start+20000]
            dist,nb=tree.query(p[ids],k=min(48,len(p)),workers=1)
            if dist.ndim==1:dist=dist[:,None];nb=nb[:,None]
            neighbour_count=np.sum(dist<h*1.12,axis=1)
            self.isolated[ids]=np.where(self.isolated[ids],neighbour_count<8,neighbour_count<5)
            valid=dist<h*1.8
            weight=np.maximum(0,1-(dist/(h*1.8))**3)*valid
            total=np.maximum(weight.sum(axis=1),1e-8)
            points=p[nb]
            mean=np.einsum('nk,nkj->nj',weight,points)/total[:,None]
            delta=points-mean[:,None,:]
            cov=np.einsum('nk,nki,nkj->nij',weight,delta,delta)/total[:,None,None]
            # Normalize PCA to unit determinant before mixing it with transported
            # material shape. Each term is SPD, so their convex blend stays SPD.
            eig,Q=np.linalg.eigh(cov)
            eig=np.maximum(eig,(h*.12)**2)
            eig=np.maximum(eig,eig[:,-1,None]/(3.8**2))
            eig/=np.maximum(np.prod(eig,axis=1)**(1/3),1e-14)[:,None]
            normalized=np.einsum('nik,nk,njk->nij',Q,eig,Q)
            transported=np.zeros_like(normalized)
            transported[:,0,0]=history[ids,0];transported[:,1,1]=history[ids,1];transported[:,2,2]=history[ids,2]
            transported[:,0,1]=transported[:,1,0]=history[ids,3]
            transported[:,0,2]=transported[:,2,0]=history[ids,4]
            transported[:,1,2]=transported[:,2,1]=history[ids,5]
            history_weight=self.config.get('surfaceOptions',{}).get('shapeHistoryWeight',.28)
            normalized=(1-history_weight)*normalized+history_weight*transported
            values,Q=np.linalg.eigh(normalized)
            min_eigen=min(min_eigen,float(values.min()))
            std=np.sqrt(np.maximum(values,1e-4));std=np.maximum(std,std[:,-1,None]/3.8)
            axes=std/np.maximum(np.prod(std,axis=1)**(1/3),1e-8)[:,None]
            unreliable=valid.sum(axis=1)<9;axes[unreliable]=1
            maximum_axis_ratio=max(maximum_axis_ratio,float((axes[:,-1]/axes[:,0]).max()))
            inv=1/(radius*axes)**2
            matrix=np.einsum('nik,nk,njk->nij',Q,inv,Q)
            G[ids]=matrix[:,[0,1,2,0,0,1],[0,1,2,1,2,2]]
            bounds[ids]=np.sqrt(np.einsum('nik,nk->ni',Q*Q,(radius*axes)**2))
            blend=np.where(unreliable,0.,.16)[:,None]
            centers[ids]=p[ids]*(1-blend)+mean*blend;history_particles+=len(ids)
        main=~self.isolated[:len(p)]
        # A removed primary marker is rendered only in its droplet cluster,
        # never also splatted into the implicit liquid field.
        field=splat_anisotropic(centers[main],G[main],bounds[main],shape,spacing)
        field=gaussian_filter(field,.55,mode='constant').astype(np.float32)
        history_correction=0.;history_fraction=0.
        if self.previous_field is not None:
            back=self.coords.copy()
            for c,vel in enumerate([vx,vy,vz]):back[c]-=vel*(dt/spacing)
            previous=map_coordinates(self.previous_field,back,order=1,mode='constant',cval=0)
            agreement=np.exp(-np.abs(field-previous)/np.maximum(.45,field))
            influence=self.config.get('surfaceOptions',{}).get('temporalBlend',.30)*agreement*(field>.08)*(previous>.08)
            correction=influence*(previous-field)
            history_correction=float(np.sqrt(np.mean(correction**2)))
            history_fraction=float(np.mean(influence[field>.1])) if np.any(field>.1) else 0.
            field+=correction
        # Collider exclusion is rebuilt from the actual collider state at this
        # time. The mesh does not extend through the solid's geometry.
        x=self.coords[0]*spacing;y=self.coords[1]*spacing;z=self.coords[2]*spacing
        solid=(x<h*.99)|(x>extent[0]-h*.99)|(y<h*.99)|(y>extent[1]-h*.99)|(z<h*.99)|(z>extent[2]-h*.99)
        for obstacle in obstacles:
            center=obstacle['center']
            if obstacle['kind']=='sphere':solid|=(x-center[0])**2+(y-center[1])**2+(z-center[2])**2<obstacle['radius']**2
            elif obstacle['kind']=='box':solid|=(np.abs(x-center[0])<obstacle['half'][0])&(np.abs(y-center[1])<obstacle['half'][1])&(np.abs(z-center[2])<obstacle['half'][2])
        field[solid]=0
        self.previous_field=field.copy()
        drops,radii,drop_velocity,drop_counts=self.droplet_clusters(p[~main],v[~main])
        target=max(int(np.sum(main))*(h*.5)**3,1e-12)
        low=.10;high=min(5.5,float(field.max())*.97);iso=float(np.clip(self.previous_iso,low,high))
        root=[];best=None;lo_error=None;hi_error=None
        for it in range(10):
            verts,faces,_,_=marching_cubes(field,level=iso,spacing=(spacing,)*3,gradient_direction='ascent',allow_degenerate=False)
            verts=verts.astype(np.float32);faces=faces.astype(np.int32)
            volume=abs(signed_volume(verts,faces));error=(volume-target)/target
            root.append({'iso':iso,'relativeError':error})
            if best is None or abs(error)<best[0]:best=(abs(error),verts,faces,iso,volume)
            if abs(error)<.0010:break
            if volume>target:low=iso;lo_error=volume-target
            else:high=iso;hi_error=volume-target
            derivative=-np.sum(np.abs(field-iso)<.13)*spacing**3/.26
            candidate=iso-(volume-target)/min(derivative,-1e-12)
            if lo_error is not None and hi_error is not None:candidate=(low*hi_error-high*lo_error)/(hi_error-lo_error)
            iso=float(candidate if low+1e-5<candidate<high-1e-5 else (low+high)/2)
        _,verts,faces,iso,_=best;self.previous_iso=iso
        recovery=None
        if best[0]>.0015:
            # A bounded positive density threshold cannot always enclose the
            # assigned volume when FLIP markers bunch around moving obstacles.
            # Recover a volume-calibrated signed-distance interface rather than
            # silently delivering an underfilled mesh or scaling all vertices.
            # This is a GLOBAL reconstruction correction, NOT evidence that the
            # particle flow has exact local mass conservation.
            mask=field>iso
            inside=distance_transform_edt(mask);outside=distance_transform_edt(~mask)
            sdf=np.where(mask,inside-.5,.5-outside).astype(np.float32)*spacing
            sdf=gaussian_filter(sdf,.4).astype(np.float32)
            allowed=np.minimum(np.minimum(np.minimum(x-h*.99,extent[0]-h*.99-x),np.minimum(y-h*.99,extent[1]-h*.99-y)),np.minimum(z-h*.99,extent[2]-h*.99-z)).astype(np.float32)
            for obstacle in obstacles:
                c=obstacle['center']
                if obstacle['kind']=='sphere':boundary=np.sqrt((x-c[0])**2+(y-c[1])**2+(z-c[2])**2)-obstacle['radius']
                else:
                    qx=np.abs(x-c[0])-obstacle['half'][0];qy=np.abs(y-c[1])-obstacle['half'][1];qz=np.abs(z-c[2])-obstacle['half'][2]
                    boundary=np.sqrt(np.maximum(qx,0)**2+np.maximum(qy,0)**2+np.maximum(qz,0)**2)+np.minimum(np.maximum(np.maximum(qx,qy),qz),0)
                allowed=np.minimum(allowed,boundary)
            left=-2*h;right=2*h;recovery_best=None;recovery_steps=[]
            for iteration in range(17):
                shift=(left+right)*.5
                candidate=np.minimum(sdf+shift,allowed).astype(np.float32)
                rv,rf,_,_=marching_cubes(candidate,level=0.,spacing=(spacing,)*3,gradient_direction='ascent',allow_degenerate=False)
                rv=rv.astype(np.float32);rf=rf.astype(np.int32);volume=abs(signed_volume(rv,rf));error=(volume-target)/target
                recovery_steps.append({'offsetMeters':shift,'relativeError':error})
                if recovery_best is None or abs(error)<recovery_best[0]:recovery_best=(abs(error),rv,rf,candidate,shift)
                if abs(error)<.0001:break
                if volume<target:left=shift
                else:right=shift
            if recovery_best[0]>.001:raise RuntimeError('Signed-distance volume-recovery bracket failed; nominal volume cannot be hidden.')
            _,verts,faces,field,offset=recovery_best;iso=0.
            recovery={'method':'volume-calibrated signed-distance offset, analytically clipped to solid/domain distance','densitySurfaceRelativeErrorBeforeRecovery':best[0],'offsetMeters':offset,'offsetInGridCells':offset/h,'iterations':recovery_steps,'localMassConservationClaim':False}
        verts,_=smooth_mesh(verts,faces,3)
        if signed_volume(verts,faces)<0:faces=faces[:,[0,2,1]]
        geometric_normals,area=normals_area(verts,faces)
        before_correction=abs(signed_volume(verts,faces));offset_total=0.
        for _ in range(3):
            current=abs(signed_volume(verts,faces))
            distance=np.clip((target-current)/max(area,1e-12),-.12*spacing,.12*spacing)
            verts+=geometric_normals*distance;offset_total+=float(abs(distance))
            if recovery is not None:
                verts=clip_geometry(verts,extent,h)
                for obstacle in obstacles:
                    if obstacle['kind']=='sphere':
                        delta=verts-np.asarray(obstacle['center'],np.float32);length=np.linalg.norm(delta,axis=1);radius=obstacle['radius']+h*.002;inside=length<radius
                        verts[inside]=np.asarray(obstacle['center'])+delta[inside]*(radius/np.maximum(length[inside],1e-12))[:,None]
            geometric_normals,area=normals_area(verts,faces)
            if abs(current-target)/target<.0003:break
        # Field-gradient normals give a smooth, consistent shading orientation.
        grad=np.gradient(gaussian_filter(field,.45),spacing)
        normal=np.column_stack([-sample(g,verts,spacing) for g in grad])
        length=np.linalg.norm(normal,axis=1);bad=length<1e-10
        normal[~bad]/=length[~bad,None];normal[bad]=geometric_normals[bad]
        inverted=np.sum(normal*geometric_normals,axis=1)<0;normal[inverted]*=-1
        normal=.78*normal+.22*geometric_normals
        normal/=np.maximum(np.linalg.norm(normal,axis=1),1e-12)[:,None]
        normal=normal.astype(np.float32)
        volume=abs(signed_volume(verts,faces));drop_volume=float(np.sum(drop_counts)*(h*.5)**3)
        # Evaluate representation after the actual 16-bit file quantization too.
        encoded=np.rint(np.clip(verts/extent,0,1)*65535).astype(np.uint16).astype(np.float32)*extent/65535
        encoded_volume=abs(signed_volume(encoded,faces))
        stats={'kernel':'transported SPD/PCA blend; temporally advected scalar reconstruction',
            'volumeRecovery':recovery,'anisotropicParticles':history_particles,'maximumAxisRatio':maximum_axis_ratio,'minimumBlendEigenvalue':min_eigen,
            'historyFieldRMSCorrection':history_correction,'meanHistoryInfluence':history_fraction,
            'targetMeshVolume':target,'signedMeshVolume':volume,'encodedMeshVolume':encoded_volume,
            'meshVolumeRelativeError':(volume-target)/target,'encodedVolumeRelativeError':(encoded_volume-target)/target,
            'nominalParticleVolume':len(p)*(h*.5)**3,'primaryDropletVolume':drop_volume,
            'dropletPrimaryMarkers':int(np.sum(~main)),'dropletClusters':len(drops),'meshedPrimaryMarkers':int(np.sum(main)),
            'primaryRepresentationSetsDisjoint':True,'totalRepresentedVolumeError':(volume+drop_volume-len(p)*(h*.5)**3)/(len(p)*(h*.5)**3),
            'normalMaximumLengthError':float(np.abs(np.linalg.norm(normal,axis=1)-1).max()),
            'normalFallbackVertices':int(np.sum(bad)),'normalVolumeCorrectionDistance':offset_total,
            'rootIterations':len(root),'volumeRoot':root,'isovalue':iso,'preCorrectionMeshVolume':before_correction}
        self.frame+=1
        return field,(vx,vy,vz),verts,normal,faces,drops,radii,drop_velocity,iso,stats

def encode(path,verts,normals,faces,drops,radii,white,diagnostic,extent,foam,caustic):
    def p16(a):return np.rint(np.clip(a/extent,0,1)*65535).astype('<u2').tobytes()
    h,w,_=caustic.shape
    body=struct.pack('<8I',0x43465234,len(verts),len(faces),len(drops),len(white),len(diagnostic),w,h)
    body+=p16(verts)+np.rint(np.clip(normals,-1,1)*32767).astype('<i2').tobytes()
    body+=np.rint(np.clip(foam,0,1)*255).astype('u1').tobytes()+faces.astype('<u4').tobytes()
    body+=p16(drops)+radii.astype('<f4').tobytes()
    body+=np.asarray(white,dtype='<f4').tobytes()+p16(diagnostic)+caustic.tobytes()
    with gzip.open(path,'wb',compresslevel=3) as f:f.write(body)
    return hashlib.sha256(body).hexdigest()

def main(name,limit=None):
    folder=ROOT/'cache'/name;manifest=json.loads((folder/'manifest.json').read_text());config=manifest['config']
    if manifest.get('schema')!='cybr-flip-cache/3':raise RuntimeError('Refusing to render an old simulation as III')
    rec=Reconstruction(config);ww=DiffuseWhitewater(config['seed']+501)
    stats=[];started=time.time()
    frames=manifest['frames'] if limit is None else manifest['frames'][:limit]
    for info in frames:
        f=info['frame'];n=info['particles']
        raw=np.fromfile(folder/f'{f:04d}.particles',dtype='<f4')
        if raw.size!=n*6:raise ValueError('Primary cache length mismatch')
        p=raw[:n*3].reshape(-1,3);v=raw[n*3:].reshape(-1,3)
        history=np.fromfile(folder/f'{f:04d}.shape',dtype='<f4').reshape(n,6)
        result=rec.reconstruct(p,v,history,info.get('colliders',config['obstacles']),manifest['frameDt'])
        field,vel,verts,normals,faces,drops,radii,drop_velocity,iso,measure=result
        # The inherited one-way whitewater classifier expects a positive
        # density threshold. Map signed distance monotonically for that model,
        # rather than supplying zero thresholds that erase its foam band.
        ww_field=np.exp(np.clip(field/(rec.h*.5),-8,8)).astype(np.float32) if measure['volumeRecovery'] is not None else field
        ww_iso=1. if measure['volumeRecovery'] is not None else iso
        white=ww.step(p,v,ww_field,vel,rec.spacing,rec.h,manifest['frameDt'],ww_iso,rec.extent,info.get('colliders',config['obstacles']),name not in ['viscous','capillary'])
        foam=np.zeros(len(verts),np.float32)
        if len(white):
            fp=white[white[:,4]==0]
            if len(fp):
                dist,ids=cKDTree(fp[:,:3]).query(verts,k=min(8,len(fp)),workers=1)
                if dist.ndim==1:dist=dist[:,None];ids=ids[:,None]
                kernel=np.maximum(0,1-dist/(rec.h*1.1))**3
                foam=1-np.exp(-np.sum(kernel*fp[ids,5],axis=1)*.58)
        diagnostic=p[np.linspace(0,len(p)-1,min(26000,len(p))).astype(int)]
        caustic,photon_stats=caustics(verts,normals,faces,field,iso,rec.extent,rec.h)
        path=folder/f'{f:04d}.mesh.gz';digest=encode(path,verts,normals,faces,drops,radii,white,diagnostic,rec.extent,foam,caustic)
        entry={'frame':f,'vertices':len(verts),'triangles':len(faces),'primaryDroplets':len(drops),'secondaryParticles':len(white),
            'foam':int(np.sum(white[:,4]==0)),'spray':int(np.sum(white[:,4]==1)),'bubbles':int(np.sum(white[:,4]==2)),
            'bytes':path.stat().st_size,'payloadSha256':digest,'caustics':photon_stats,**measure}
        stats.append(entry)
        if f in (0,36,72,95):np.savez_compressed(folder/f'{f:04d}.surface.npz',positions=verts,normals=normals,indices=faces,drops=drops,radii=radii,drop_velocity=drop_velocity,foam=foam,white=white)
        if f%12==0:print(name,'frame',f,'triangles',len(faces),'volume%',round(measure['totalRepresentedVolumeError']*100,3),'normal error',measure['normalMaximumLengthError'],'seconds',round(time.time()-started,1),flush=True)
    manifest['meshes']=stats
    manifest['surface']={'method':'transported SPD/PCA kernels; scalar-history advection; disjoint clustered droplets; volume-corrected surface',
        'spacing':rec.spacing,'shape':list(map(int,rec.grid_shape)),'explicitSurfaceTracking':False}
    manifest['whitewater']={'method':'persistent one-way visual entrainment markers; underlying II transport retained',
        'births':ww.total_births,'deaths':ww.total_deaths,'transitions':ww.transitions,'twoWayCoupling':False,
        'secondarySprayContributesPrimaryMass':False}
    manifest['meshWallSeconds']=time.time()-started;manifest['meshingComplete']=limit is None
    target=folder/('manifest.preview.json' if limit is not None else 'manifest.json')
    target.write_text(json.dumps(manifest,indent=2));print('MESH III COMPLETE',name,manifest['meshWallSeconds'],flush=True)

if __name__=='__main__':
    main(sys.argv[1] if len(sys.argv)>1 else 'impact',int(sys.argv[2]) if len(sys.argv)>2 else None)
