"""Smooth MPM free boundary minus measured open crust gaps.

Liquid is surfaced from density, never inverted inlet quadrature cubes.
Crack voids come only from paired, separated coherent material faces. Their
widths are not enlarged for visibility. CPU manifold booleans preserve those
subcell voids instead of blurring them shut with the fluid density kernel.
"""
import hashlib,json
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull
from scipy.ndimage import map_coordinates
import manifold3d as mf
from lava_mpm_material_surface import reconstruct,crease_normals
from lava_mpm_surface import extract as kernel_extract,fields,reference_coordinates
from lava_skin import normals


def manifold(v,f,tag):
    props=np.ascontiguousarray(np.c_[v,np.full(len(v),tag)],dtype=np.float64)
    result=mf.Manifold(mf.Mesh64(props,np.ascontiguousarray(f,dtype=np.uint64)))
    if result.status()!=mf.Error.NoError:raise ValueError(('Invalid oriented surface',str(result.status())))
    return result


def prisms(paired_faces):
    """Clip linear face openings to their actual positive region."""
    result=[]
    for a,b in paired_faces:
        for ids in ([0,1,2],[0,2,3]):
            aa=a[ids];bb=b[ids];normal=np.cross(aa[1]-aa[0],aa[2]-aa[0]);normal/=max(np.linalg.norm(normal),1e-30)
            opening=(bb-aa)@normal
            if opening.max()<=1e-12:continue
            polygon=[(aa[i],bb[i],opening[i]) for i in range(3)];clipped=[]
            for first,second in zip(polygon,polygon[1:]+polygon[:1]):
                if first[2]>0:clipped.append(first)
                if (first[2]>0)!=(second[2]>0):
                    t=first[2]/(first[2]-second[2]);clipped.append((first[0]+t*(second[0]-first[0]),first[1]+t*(second[1]-first[1]),0.))
            points=np.unique(np.array([q for pair in clipped for q in pair[:2]]),axis=0)
            if len(points)<4 or np.linalg.matrix_rank(points-points.mean(0),tol=1e-13)<3:continue
            hull=ConvexHull(points);f=hull.simplices.copy();n=np.cross(points[f[:,1]]-points[f[:,0]],points[f[:,2]]-points[f[:,0]])
            flip=np.einsum('ij,ij->i',n,hull.equations[:,:3])<0;f[flip]=f[flip][:,[0,2,1]]
            result.append((points,f))
    return result


def subtract_gaps(v,f,paired_faces):
    base=manifold(v,f,0.);gaps=prisms(paired_faces);union=None
    for points,faces in gaps:
        gap=manifold(points,faces,1.);union=gap if union is None else union+gap
    result=base if union is None else base-union
    if result.status()!=mf.Error.NoError or result.volume()<=0:raise ValueError('Measured-gap boolean failed')
    mesh=result.to_mesh64();props=np.array(mesh.vert_properties);faces=np.array(mesh.tri_verts,dtype=int)
    removed=base.volume()-result.volume();void_volume=0. if union is None else union.volume()
    if removed< -1e-15 or removed>void_volume+1e-12:raise ValueError('Crack cut exceeded its measured void volume')
    return props[:,:3],faces,props[faces,3].min(1)>.5,dict(gapPrisms=len(gaps),measuredVoidVolumeM3=float(void_volume),removedVolumeM3=float(removed),watertight=True,artificialGapWideningM=0.)


def extract(path):
    path=Path(path);s=dict(np.load(path));meta=json.loads(path.with_suffix('.json').read_text());sample=np.array(meta.get('sample_size',[meta['spacing']]*3))
    material,measured=reconstruct(s,sample,measure_cracks_only=True)
    candidate=path.with_name(path.stem+'-kernel-candidate.npz');kernel_extract(path,'kernel',candidate);base=dict(np.load(candidate))
    v,f,crack,cut=subtract_gaps(base['v'],base['f'],material['gap_faces'])
    dx=sample*.35;lo,dx,field=fields(s,dx,sample.max()*.5/dx,np.ones(3)*1.4);coords=((v-lo)/dx).T
    attrs={name:map_coordinates(field[name],coords,order=1,mode='nearest') for name in ['temperature','solid','damage']}
    rest,nearest=reference_coordinates(v,s,dx)
    out=dict(v=v,f=f,normal=normals(v,f),rest=rest,uv=rest[:,:2],component=s.get('labels',np.zeros(len(s['x']),int))[nearest],crack_face=crack,**attrs)
    out=crease_normals(out)
    for key in ['camera_eye','camera_target','camera_fov','time']:out[key]=base[key]
    volume=float(np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))/6);target=float(s['volume'].sum());error=abs(volume-target)/target
    if error>.02:raise ValueError(('Measured-gap surface volume differs from solved volume',error))
    dest=path.with_name(path.stem+'-surface.npz');np.savez_compressed(dest,**out)
    report=dict(method='density free boundary with measured coherent crack voids',source=str(path),sourceSha256=hashlib.sha256(path.read_bytes()).hexdigest(),physicalSeconds=float(s['time']),vertices=len(out['v']),triangles=len(out['f']),
        fractureTopologyPreserved=True,openFacePairs=measured['openFacePairs'],crackWallTriangles=int(crack.sum()),maximumOpeningM=measured['maximumOpeningM'],
        solverParticleVolumeM3=target,reconstructedVolumeM3=volume,relativeVolumeDifference=error,maximumDeformationCondition=measured['maximumCoherentDeformationCondition'],
        excludedLiquidCellInversions=measured['invertedLiquidCellsExcludedFromCrackMeasurement'],crackMeasurement=measured,cut=cut,
        limits='Liquid cells are not rendered as solid cubes. Only actual positive face gaps are cut. This coarse surface is not spatially converged and local solid deformation remains a validation requirement.')
    dest.with_suffix('.json').write_text(json.dumps(report,indent=2));return dest
