"""Surface cooling from cohesive-shell exposure history, entirely on CPU.

Radiative/conductive enthalpy columns supply exposed surface temperatures.
A distance-based lateral boundary-layer approximation cools melt adjacent
to crust. Pre-existing small vents retain an authored older exposure age.
"""
from pathlib import Path
import os,time,json
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='2')
import numpy as np
from scipy.ndimage import map_coordinates,distance_transform_edt
from scipy.special import erf
from lava_geometry_preview import raster
from lava_cohesive_cpu import noise
from lava_thermal import columns
from lava_skin import normals

R=Path(__file__).resolve().parent/'lava-focus/cohesive'

def subdivide(v,f,temperature):
    edges=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]);unique,ix=np.unique(np.sort(edges,axis=1),axis=0,return_inverse=True);mid=ix.reshape(3,-1).T+len(v)
    out=np.concatenate([v,v[unique].mean(1)]);a,b,c=f.T;ab,bc,ca=mid.T
    return out,np.concatenate([np.c_[a,ab,ca],np.c_[ab,b,bc],np.c_[ca,bc,c],np.c_[ab,bc,ca]]),np.r_[temperature,temperature[unique].mean(1)]

def main():
    start=time.time();a=dict(np.load(R/'shell-detailed.npz'));m=np.load(R/'shell-03-mechanics.npz')
    v=a['v'];f=a['f'];lo=v[:,:2].min(0)-.01;dx=.0025;shape=np.ceil((v[:,:2].max(0)+.01-lo)/dx).astype(int)+1
    def cover(x,faces):
        p=np.c_[(x[:,:2]-lo)/dx,-x[:,2]]
        return raster(p,faces,np.full((len(faces),3),255,dtype='u1'),int(shape[0]),int(shape[1]))[:,:,0]>0
    occupancy=[cover(x,m['f']) for x in m['captures']]
    skin=a['component'][f].all(1);covered=cover(v,f[skin])
    duration=float(m['history'][-1,0]);times=np.array([1,51,101,150])/180
    age=np.full(covered.shape,20.)
    for i in range(3):age[occupancy[i]]=max(.025,duration-(times[i]+times[i+1])*.5)
    # Surviving shell faces that were perforated by the fine-detail stage
    # are old vents, separate from fresh mechanically opened tears.
    yy,xx=np.indices(covered.shape);world=np.c_[lo[0]+xx.ravel()*dx,lo[1]+yy.ravel()*dx,np.zeros(xx.size)]
    variation=noise(world,8.5,889).reshape(age.shape)
    older_vents=occupancy[-1]&~covered
    age[older_vents]=np.clip(5.5+3.0*variation[older_vents],1.8,14.)
    distance=distance_transform_edt(~covered)*dx
    ages=np.geomspace(.002,40,192);thermal,error=columns(ages,np.full(len(ages),1450.))
    temp=np.interp(age,ages,thermal)
    boundary=2*np.sqrt(5e-7*np.maximum(age,.1))
    temp=1180+(temp-1180)*erf(distance/np.maximum(boundary,.0015))
    temp[covered]=1450
    core_vertices=np.where(a['component']==0)[0];ncore=len(core_vertices);core_faces=f[~skin]
    assert core_vertices[-1]==ncore-1
    bv,bf,perimeter_cap=subdivide(v[:ncore],core_faces,a['temperature'][:ncore])
    bn=normals(bv,bf);top=(bv[:,2]>0)&(bn[:,2]>.08)
    coords=np.array([(bv[:,1]-lo[1])/dx,(bv[:,0]-lo[0])/dx])
    bt=np.full(len(bv),850.);bt[top]=np.minimum(perimeter_cap[top],map_coordinates(temp,coords[:,top],order=1,mode='nearest'))
    # Millimetre-scale molten relief is separate from the overlying shell.
    # Its amplitude is below the shell-to-foundation clearance.
    relief=.0012*noise(bv,34,651)+.00045*noise(bv,82,217)
    bv[top]+=bn[top]*relief[top,None];bn=normals(bv,bf)
    sv=v[ncore:];sf=f[skin]-ncore
    output=R/'shell-thermal.npz'
    np.savez_compressed(output,v=np.concatenate([bv,sv]).astype('f4'),f=np.concatenate([bf,sf+len(bv)]).astype('i4'),normal=np.concatenate([bn,a['normal'][ncore:]]).astype('f4'),rest=np.concatenate([bv,a['rest'][ncore:]]).astype('f4'),temperature=np.r_[bt,a['temperature'][ncore:]].astype('f4'),component=np.r_[np.zeros(len(bv)),np.ones(len(sv))].astype('u1'))
    assert np.isfinite(bt).all()
    report={'device':'CPU','seconds':round(time.time()-start,2),'exposureGrid':shape.tolist(),'simulationSeconds':duration,'surfaceTemperatureK':np.quantile(temp[~covered],[0,.1,.5,.9,1]).tolist(),'columnEnergyRelativeError':error,'coreVertices':len(bv),'coreTriangles':len(bf),'method':'Four mechanical exposure snapshots + natural enthalpy-column cooling + analytic lateral edge boundary layer','limits':['Exposure onset is bracketed by four snapshots','Old fine vents have authored pre-shot ages','Lateral cooling is a boundary-layer approximation rather than a 3D heat solve']}
    output.with_suffix('.json').write_text(json.dumps(report,indent=2));np.savez_compressed(R/'exposure-fields.npz',temperature=temp,age=age,covered=covered,olderVents=older_vents,lo=lo,spacing=dx)
    print(json.dumps(report))

if __name__=='__main__':main()
