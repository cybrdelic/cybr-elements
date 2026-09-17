"""Verify nonzero inlet, reflected corners, moving contact, and source ledgers."""
import json
import numpy as np
from scipy.sparse import diags,coo_matrix,csr_matrix
from lava_mpm import ROOT,MPM,block,basis
from lava_mpm_inlet import velocity_map,profile,columns,emit,conduit_constraints
from lava_mpm_fracture import implicit_contact


def main():
    config=dict(plane=-.08,half_width=.015,height=.025,peak_speed=.08,temperature=1450.)
    dx=.01;origin=np.array([-.10,-.03,-.02]);shape=np.array([7,7,9])
    xyz=origin+np.array(np.unravel_index(np.arange(np.prod(shape)),shape)).T*dx
    S,lift=velocity_map(xyz,dx,np.zeros(len(xyz),dtype=int),config)
    rng=np.random.default_rng(19);u=(S@rng.normal(0,.05,S.shape[1])+lift).reshape(-1,3)
    yz=np.array(np.meshgrid(np.linspace(-.01,.01,5),np.linspace(.0025,.03,5),indexing='ij')).reshape(2,-1).T
    x=np.c_[np.full(len(yz),config['plane']),yz];ids,w,g,dp=basis(x,dx,origin,shape)
    at_plane=np.sum(w[:,:,None]*u[ids],axis=1)
    z=xyz[ids,2];expected=np.sum(w*profile(xyz[ids,1],abs(z),config)*np.where(z<0,-1,1),axis=1)
    boundary_error=float(np.max(abs(at_plane-np.c_[expected,np.zeros((len(x),2))])))
    assert boundary_error<1e-12
    x[:,0]=-.065;x[:,2]=0;ids,w,_,_=basis(x,dx,origin,shape)
    ground_error=float(np.max(abs(np.sum(w[:,:,None]*u[ids],axis=1))));assert ground_error<1e-12
    # A moving prescribed wall pushes a free mass through unilateral contact.
    A=diags(np.ones(6));lift=np.array([.1,0,0,0,0,0]);S=coo_matrix((np.ones(3),(np.arange(3,6),np.arange(3))),shape=(6,3)).tocsr();C=csr_matrix([[1.,0,0,-1.,0,0]])
    v,res,mult,_,_=implicit_contact(A,-A@lift,S,C,1e-12,C@lift);v+=lift
    assert abs(v[3]-.1)<1e-10 and mult[0]>0 and res<1e-10
    s=MPM(block([-.03,-.01,.02],[0,.01,.04],.005),.005,.01,origin=[-.10,-.06,-.02],shape=[24,14,16],temperature=1450,gravity=(0,0,0))
    mass0=s.mass.sum();energy0=float(s.mass@s.h);yz,speed=columns(s.spacing,s.dx,config);duration=0.
    for dt in (.012,.031,.007):emit(s,config,dt);duration+=dt
    expected_mass=s.material.density*s.spacing**2*speed.sum()*duration
    mass_error=float(abs(s.mass.sum()-mass0-expected_mass));energy_error=float(abs(s.mass@s.h-energy0-expected_mass*s.material.enthalpy(1450.)))
    assert mass_error<1e-12 and energy_error<1e-8
    assert len(np.unique(s.rest,axis=0))==len(s.rest),'Repeated inlet emissions reused material identities'
    emitted=int(s.ledger['inlet_particles'])
    domain_error=float(np.max(abs(np.linalg.det(s.F[-emitted:])*np.prod(s.sample_size)-s.volume[-emitted:])))
    assert domain_error<1e-18,'Source deformation must retain the prescribed flux volume'
    # An outward-moving material point must stop exactly at the rigid pipe
    # wall. A downstream point at the same y must remain unconstrained.
    cfg={**config,'pipe_end':-.05};x=np.array([[-.06,.014,.0125],[-.04,.014,.0125]])
    velocity=np.array([[0,.2,0],[0,.2,0]]);local=np.array([np.zeros(27,int),np.ones(27,int)]);w=np.full((2,27),1/27)
    C,bound=conduit_constraints(x,velocity,local,w,2,.01,.02,cfg)
    assert C.shape[0]==1
    solution,wall_res,_,_,_=implicit_contact(diags(np.ones(6)),velocity.ravel(),diags(np.ones(6)),C,1e-12,-bound)
    wall_position=x+.02*solution.reshape(-1,3);wall_error=float(abs(wall_position[0,1]-.015))
    assert wall_error<1e-10 and abs(solution[4]-.2)<1e-12
    result=dict(status='pass',inletVelocityError=boundary_error,groundVelocityError=ground_error,movingWallVelocityError=float(abs(v[3]-.1)),sourceMassErrorKg=mass_error,sourceEnthalpyErrorJ=energy_error,sourceQuadratureFluxM3PerS=float(expected_mass/s.material.density/duration),limits='Verifies discrete boundary and source accounting, not grid convergence or final lava quality')
    result.update(conduitPositionErrorM=wall_error,conduitDownstreamUnconstrained=True)
    result.update(uniqueMaterialReferenceCells=True,sourceMaterialDomainVolumeErrorM3=domain_error)
    out=ROOT/'validation'/'inlet_source.json';out.write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':main()
