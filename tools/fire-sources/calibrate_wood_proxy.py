"""Correct finite wood inventory without changing approved collision geometry.

Wood mass follows the explicitly reduced MODEL-metre beam graph. Tree laminae
use reviewed triangle area times an authoring LMA .05kg/m², not a species fit.
Capacity 1.5 denotes full495kg/m³ wood; all void capacities are zero. The same
quantized inventory supplies thermal/gas transfer and structural loads.
"""
from pathlib import Path
import argparse,json
import numpy as np
from scipy.spatial import cKDTree
from export_wood_structure import distribute_proxy_mass,digest

ROOT=Path(__file__).resolve().parents[2];OBJECTS=ROOT/'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/objects'
CELL=3/64;DENSITY=495

def allocate(target,counts,parent,nodes,owners,valid):
    budget=np.zeros(len(target),np.float64);maximum=counts*DENSITY*CELL**3;unresolved=0.0
    points=np.argwhere(valid)[:,[2,1,0]];positions=(points+.5)*CELL-1.5;tree=cKDTree(positions)
    receiver=owners[valid.reshape(-1)]
    for i,mass in enumerate(target):
        remaining=float(mass);p=i
        while remaining>1e-14 and p>=0:
            put=min(remaining,max(maximum[p]-budget[p],0));budget[p]+=put;remaining-=put;p=int(parent[p])
        if remaining>1e-14:
            unresolved+=remaining;_,near=tree.query(nodes[i],k=min(64,len(positions)))
            for q in np.atleast_1d(near):
                p=int(receiver[q]);put=min(remaining,max(maximum[p]-budget[p],0));budget[p]+=put;remaining-=put
                if remaining<1e-14:break
            if remaining>1e-12:
                # Rare fallback: finite capacity remains, so choose nearest
                # available OWNER, rather than dropping unrepresented mass.
                available=np.flatnonzero(maximum-budget>remaining)
                if not len(available):raise ValueError('Geometry cannot represent finite mass at physical density')
                p=int(available[np.argmin(np.linalg.norm(nodes[available]-nodes[i],axis=1))]);budget[p]+=remaining
    return budget,unresolved

def leaf_mass(folder,count):
    v=np.fromfile(folder/'vertices.bin',dtype='<f4').reshape(-1,9);f=np.fromfile(folder/'indices.bin',dtype='<u4').reshape(-1,3);o=np.fromfile(folder/'owners.bin',dtype='<u4').reshape(-1,2)[:,0]
    use=np.all(v[f,8]==8,axis=1);tri=v[f[use],:3];area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)*.5
    return np.bincount(o[f[use,0]],weights=area*.05,minlength=count),float(area.sum())

def fix(name,folder,source,destination,leaf=False):
    d=OBJECTS/folder;m=json.loads((d/'manifest.json').read_text());s=np.fromfile(d/'nodes.bin',dtype='<f4').reshape(-1,16);owners=np.fromfile(d/'voxel-owners.bin',dtype='<u4')
    massfile=d/'analytic-mass.bin'
    if not massfile.exists():s[:,8].astype('<f4').tofile(massfile)
    analytic=np.fromfile(massfile,dtype='<f4').astype(np.float64);parent=s[:,3].astype(int);raw=np.fromfile(OBJECTS/source,dtype='<f2').astype(np.float64).reshape(64,64,64,4);result=raw.copy()
    mat=raw[...,3];wood=(raw[...,1]>0)&(mat>.5)&(mat<2.5)&(raw[...,0]<=0);foliage=(raw[...,1]>0)&(mat>7.5)&(raw[...,0]<.07)
    counts=np.bincount(owners[wood.reshape(-1)],minlength=len(s));budget,unresolved=allocate(analytic,counts,parent,s[:,:3],owners,wood)
    fraction=np.divide(budget,counts*DENSITY*CELL**3,out=np.zeros(len(s)),where=counts>0)
    result[...,1]=0;flat=result.reshape(-1,4);flat[wood.reshape(-1),1]=1.5*fraction[owners[wood.reshape(-1)]]
    leafproof=None
    if leaf:
        target,area=leaf_mass(d,len(s));counts=np.bincount(owners[foliage.reshape(-1)],minlength=len(s));leafbudget,leafunresolved=allocate(target,counts,parent,s[:,:3],owners,foliage)
        leaffraction=np.divide(leafbudget,counts*DENSITY*CELL**3,out=np.zeros(len(s)),where=counts>0)
        flat[foliage.reshape(-1),1]=1.5*leaffraction[owners[foliage.reshape(-1)]]
        leafproof={'reviewedTriangleAreaM2':area,'authoringDryLeafKgM2':.05,'targetMassKg':float(target.sum()),'unresolvedMassReassignedKg':leafunresolved,'reference':'Wright et al.(2004), Nature428:821–827,doi:10.1038/nature02403','limit':'Specimen/species not fitted; .05kg/m² is explicit authoring choice within reported cross-species range.'}
    quantized=result.astype('<f2');proof=distribute_proxy_mass(s,owners,quantized)
    proof.update({'id':name,'woodTargetMassKg':float(analytic.sum()),'unresolvedWoodMassReassignedKg':unresolved,'leaf':leafproof,'approvedCollisionThermalMaterialExact':bool(np.array_equal(quantized[...,[0,2,3]],raw.astype('<f2')[...,[0,2,3]])),'capacityFullDensity':1.5,'densityKgM3':495,'voidCapacityZero':bool(np.all(quantized[...,1][~(wood|foliage)]==0))})
    if not proof['approvedCollisionThermalMaterialExact']:raise ValueError('Collision geometry changed')
    dst=OBJECTS/destination;quantized.tofile(dst);s.astype('<f4').tofile(d/'nodes.bin')
    m['massCalibration']=proof;m['analyticMassFile']='analytic-mass.bin';m['thermalProxy']=str(dst.relative_to(d)).replace('\\','/') if dst.is_relative_to(d) else '../'+dst.name
    for path in [d/'nodes.bin',massfile]:m['files'][path.name]={'bytes':path.stat().st_size,'sha256':digest(path)}
    if dst.parent==d:m['files'][dst.name]={'bytes':dst.stat().st_size,'sha256':digest(dst)}
    else:m['thermalProxyProof']={'bytes':dst.stat().st_size,'sha256':digest(dst)}
    (d/'manifest.json').write_text(json.dumps(m,indent=2));return proof

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--only',choices=['all','tree','logs','house'],default='all');args=parser.parse_args();reports=[]
    for name,folder,source,destination,leaf in [('tree','forest-tree/structure','cybr-tree.rgba16.bin','forest-tree/wood-solid.rgba16.bin',True),('logs','logs','logs.rgba16.bin','logs/solid.rgba16.bin',False),('house','house','house.rgba16.bin','house/solid.rgba16.bin',False)]:
        if args.only in ['all',name]:reports.append(fix(name,folder,source,destination,leaf))
    if args.only=='all':
        d=OBJECTS/'wood-sigil';m=json.loads((d/'manifest.json').read_text());s=np.fromfile(d/'nodes.bin',dtype='<f4').reshape(-1,16);owners=np.fromfile(d/'voxel-owners.bin',dtype='<u4');solid=np.fromfile(d/'solid.rgba16.bin',dtype='<f2').reshape(64,64,64,4)
        if not (d/'analytic-mass.bin').exists():s[:,8].astype('<f4').tofile(d/'analytic-mass.bin')
        proof=distribute_proxy_mass(s,owners,solid);proof.update({'id':'sigil','source':'Exact native contour extruded .036m, analytic polygon/voxel intersection capacity','geometryMassKg':m['provenance']['proxyInventory']['geometryVolumeM3']*495,'densityKgM3':495,'capacityFullDensity':1.5,'approvedCollisionThermalMaterialExact':True})
        s.astype('<f4').tofile(d/'nodes.bin');m['massCalibration']=proof;m['thermalProxy']='solid.rgba16.bin'
        for p in [d/'nodes.bin',d/'analytic-mass.bin']:m['files'][p.name]={'bytes':p.stat().st_size,'sha256':digest(p)}
        (d/'manifest.json').write_text(json.dumps(m,indent=2));reports.append(proof)
    path=ROOT/'work/wood-structure-qa/capacity-calibration.json';path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(reports,indent=2));print(json.dumps([{k:p.get(k) for k in ['id','woodTargetMassKg','finiteProxyMassKg','leaf','approvedCollisionThermalMaterialExact']} for p in reports]))

if __name__=='__main__':main()
