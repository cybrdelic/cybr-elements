"""Independent metric/transfer checks for the fine-through-thickness grid."""
import json,numpy as np
from scipy.sparse import diags
from lava_mpm import ROOT,MPM,Material,basis,basis_rect,p2g,laplacian,block,heat_solve

def main():
    cell=np.array([.004,.003,.0005]);origin=-cell*3;shape=np.array([15,13,18]);rng=np.random.default_rng(341)
    x=rng.uniform(cell*2,cell*np.array([8,6,10]),(140,3));ids,w,g,dp=basis_rect(x,cell,origin,shape)
    L=np.array([[.08,.01,.03],[-.03,.06,.01],[.07,.02,-.02]]);v=x@L.T+[.03,.02,.01];C=np.tile(L,(len(x),1,1));mass=rng.uniform(.5,1.5,len(x))
    gm,mom,h=p2g(ids,w,dp,mass,v,C,np.ones(len(x)),np.prod(shape));u=mom/np.maximum(gm[:,None],1e-30)
    recovered=np.sum(w[:,:,None]*u[ids],axis=1);affine=4*np.einsum('pk,pki,pkj->pij',w,u[ids],dp)/cell[None,None,:]**2
    error=dict(partition=float(abs(w.sum(1)-1).max()),gradient=float(abs(g.sum(1)).max()),velocity=float(abs(recovered-v).max()),affine=float(abs(affine-C).max()),momentum=float(np.linalg.norm(mom.sum(0)-(mass[:,None]*v).sum(0))))
    assert max(error.values())<1e-9,error
    iso=basis(x,.004,origin,np.array([20,20,20]));rect=basis_rect(x,np.full(3,.004),origin,np.array([20,20,20]));iso_error=max(float(abs(a-b).max()) for a,b in zip(iso,rect));assert iso_error<1e-10
    shape=(6,6,9);n=np.prod(shape);fill=np.ones(n);K=laplacian(shape,np.ones(n,bool),fill,.004,1.6,cell)
    assert abs(K.sum(0)).max()<1e-12
    # A Fourier mode has a known finite-volume eigenvalue with Neumann walls.
    q=np.indices(shape)[2].ravel();mode=np.cos(np.pi*(q+.5)/shape[2]);eigen=4*1.6*np.prod(cell)/cell[2]**2*np.sin(np.pi/(2*shape[2]))**2
    metric_error=float(abs(K@mode-eigen*mode).max());assert metric_error<1e-11
    s=MPM(block([0,0,.001],[.016,.009,.003],cell/2),.002,.004,cell_size=cell,sample_size=cell/2,origin=origin,shape=[15,13,20],ground=False)
    initial=float(s.mass@s.h);row=s.step(.1,mechanics=False);T=s.material.temperature(s.h)
    top=T[s.rest[:,2]>.0027].mean();middle=T[(s.rest[:,2]>.0016)&(s.rest[:,2]<.0024)].mean()
    assert top<middle and row['thermalBalanceRelative']<1e-8,(top,middle)
    result=dict(status='pass',transfer=error,isotropicEquivalence=iso_error,finiteVolumeMetricError=metric_error,topK=float(top),interiorK=float(middle),heatBalance=row['thermalBalanceRelative'],limits='Metric consistency and component tests; not continuum or fracture convergence.')
    (ROOT/'validation'/'rectangular_grid.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':main()
