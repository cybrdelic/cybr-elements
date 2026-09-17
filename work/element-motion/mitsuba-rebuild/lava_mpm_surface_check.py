"""Independent geometric checks; the cut coupons are tests, not lava art."""
import json
import numpy as np
from PIL import Image,ImageDraw
from lava_mpm import ROOT,MPM,block
from lava_mpm_material_surface import reconstruct,crease_normals
from lava_geometry_preview import raster


def state(s):
    return dict(x=s.x,rest=s.rest,F=s.F,volume=s.volume,
        temperature=s.material.temperature(s.h),solid=s.material.solid(s.material.temperature(s.h)),damage=s.damage,
        bond_frozen=s.connectivity.frozen,bond_edges=s.connectivity.edges,bond_broken=s.connectivity.broken)


def picture(mesh,title):
    v=mesh['v'];f=mesh['f'];eye=np.array([.019,-.025,.025]);center=np.array([0,0,.004])
    z=center-eye;z/=np.linalg.norm(z);x=np.cross(z,[0,0,1]);x/=np.linalg.norm(x);y=np.cross(x,z)
    q=(v-eye)@np.array([x,y,z]).T;w=480;h=390;fl=500
    p=np.c_[w/2+fl*q[:,0]/q[:,2],h/2-fl*q[:,1]/q[:,2],q[:,2]]
    n=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-30)
    color=np.tile([.35,.39,.43],(len(f),1))
    color[mesh['crack_face']]=[.9,.24,.06]
    color*=np.maximum(0,n@np.array([-.3,-.3,.9055]))[:,None]*.8+.2
    im=Image.fromarray(raster(p,f,(np.clip(color,0,1)**(1/2.2)*255).astype('u1'),w,h))
    d=ImageDraw.Draw(im);d.text((16,12),title,fill='#d0d0d0');return im


def main():
    folder=ROOT/'surface-proof-22';folder.mkdir(exist_ok=True)
    sp=.001;x=block([-.006,-.006,.001],[.006,.006,.005],sp)
    s=MPM(x,sp,sp*2,temperature=1050.,ground=False)
    s.connectivity.update(x,np.ones(len(x)),s.damage,s.principal_direction,sp,.65)
    original=state(s);intact,ri=reconstruct(original,np.full(3,sp))
    expected=.012*.012*.004
    assert abs(ri['reconstructedVolumeM3']/expected-1)<1e-12
    assert ri['openFacePairs']==0 and ri['crackWallTriangles']==0
    # Analytic affine motion/volume; independent of any MPM solver step.
    A=np.array([[1.1,.12,0],[0,.9,.05],[0,0,1.04]])
    affine={k:v.copy() for k,v in original.items()};affine['x']=x@A.T+[.002,-.001,.001]
    affine['F']=np.tile(A,(len(x),1,1));affine['volume']*=np.linalg.det(A)
    ma,ra=reconstruct(affine,np.full(3,sp))
    affine_error=float(abs(ra['reconstructedVolumeM3']/(expected*np.linalg.det(A))-1))
    assert affine_error<1e-12 and ra['maximumCellVolumeRelativeError']<1e-11
    # A partial crack: still globally attached beyond y=3 mm. This is an
    # explicitly prescribed unit-test cut, not a simulated failure claim.
    a,b=s.connectivity.edges.T
    s.connectivity.broken=(x[a,0]*x[b,0]<0)&(np.maximum(x[a,1],x[b,1])<.003)
    cut=state(s);closed,rc=reconstruct(cut,np.full(3,sp))
    assert rc['globalMaterialComponents']==1
    assert rc['brokenFacePairs']>0 and rc['openFacePairs']==0
    assert rc['crackWallTriangles']==0,'Closed cracks must not create cosmetic lines'
    assert abs(rc['reconstructedVolumeM3']/expected-1)<1e-12
    # Known opening away from the tip; geometry must retain exactly 0.8 mm
    # without needing global components to separate.
    moved={k:v.copy() for k,v in cut.items()}
    taper=np.clip((.003-x[:,1])/.003,0,1)
    moved['x'][:,0]+=.0004*np.sign(x[:,0])*taper
    opened,ro=reconstruct(moved,np.full(3,sp))
    assert ro['globalMaterialComponents']==1
    assert ro['openFacePairs']>0 and ro['crackWallTriangles']>0
    pairs=np.asarray(ro['openingPairs']);gap=np.asarray(ro['openingM'])
    far=np.max(x[pairs,1],axis=1)<-.002
    assert far.any() and np.max(abs(gap[far]-.0008))<1e-12,(ro['maximumOpeningM'],gap[far].tolist())
    assert ro['minimumCellVolumeM3']>0
    # Reference positions must remain material coordinates, even after
    # motion; component must be categorical rather than solid fraction.
    assert np.issubdtype(opened['component'].dtype,np.integer)
    assert np.max(abs(opened['v']-opened['rest']))>.0003
    smooth=crease_normals({k:v.copy() for k,v in opened.items()})
    assert np.array_equal(smooth['v'][smooth['f']],opened['v'][opened['f']]),'Shading must not move fracture geometry'
    crack_vertices=set(smooth['f'][smooth['crack_face']].ravel())
    outer_vertices=set(smooth['f'][~smooth['crack_face']].ravel())
    assert crack_vertices.isdisjoint(outer_vertices),'Crack walls share smoothed outer normals'
    canvas=Image.new('RGB',(1440,430));draw=ImageDraw.Draw(canvas)
    for i,(m,title) in enumerate([(intact,'Intact material'),(closed,'Closed partial crack: no added line'),(opened,'Open partial crack: attached at the tip')]):
        canvas.paste(picture(m,title),(i*480,0))
    draw.text((16,402),'CPU geometry unit tests. Prescribed test cuts and displacement; NOT a lava simulation or final appearance.',fill='#999')
    canvas.save(folder/'surface-tests.png')
    result=dict(status='pass',intact=ri,closed=rc,opened=ro,affineVolumeRelativeError=affine_error,
                farFromTipOpeningErrorM=float(np.max(abs(gap[far]-.0008))),creaseShadingPreservesGeometry=True,
                proof=str(folder/'surface-tests.png'),fixture='prescribed geometric validation coupon, never published as simulated lava')
    (ROOT/'validation/material_surface.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(status='pass',affineVolumeRelativeError=affine_error,partialCrackOpenM=ro['maximumOpeningM'],globalComponents=ro['globalMaterialComponents'],proof=str(folder/'surface-tests.png'))))


if __name__=='__main__':main()
