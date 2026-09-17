"""A viscous MPM lava front carrying pre-existing basalt fragments.

The initial fragments are authored, not solver-generated cracks. Subsequent
positions come from two-way MPM / XPBD rigid contact. No animated positions.
Coupling kernels follow Newton's Apache-2.0 example_mpm_twoway_coupling.
"""
import os
from pathlib import Path
ROOT=Path(__file__).parent/'lava-focus/mpm/rebuild-29'
(ROOT/'temp').mkdir(parents=True,exist_ok=True)
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',TEMP=str(ROOT/'temp'),TMP=str(ROOT/'temp'))
import argparse,json,time,hashlib
import numpy as np
from scipy.spatial import ConvexHull
import warp as wp
import newton
from newton.solvers import SolverImplicitMPM, SolverXPBD
from newton._src.solvers.implicit_mpm import implicit_mpm_model as mpm_geometry
from lava_newton28_thermal import heat_step,temperature
wp.config.kernel_cache_dir=str(ROOT.parent/'rebuild-28/warp-cache')
wp.config.use_precompiled_headers=False
# Newton 1.6's MPM extractor omits CONVEX_MESH although it has the same
# triangle source as MESH. Preserve rigid GJK hull contact while exposing
# those identical triangles to MPM. This adapter changes no geometry.
_shape_mesh=mpm_geometry._get_shape_mesh
def convex_mpm_mesh(model,sid,kind,scale):
    return _shape_mesh(model,sid,newton.GeoType.MESH if kind==newton.GeoType.CONVEX_MESH else kind,scale)
mpm_geometry._get_shape_mesh=convex_mpm_mesh

@wp.kernel
def body_forces(dt:float,ids:wp.array[int],imp:wp.array[wp.vec3],pos:wp.array[wp.vec3],bid:wp.array[int],q:wp.array[wp.transform],com:wp.array[wp.vec3],force:wp.array[wp.spatial_vector]):
    i=wp.tid();cid=ids[i]
    if cid>=0 and cid<bid.shape[0]:
        b=bid[cid]
        if b>=0:
            f=imp[i]/dt;r=pos[i]-wp.transform_point(q[b],com[b])
            wp.atomic_add(force,b,wp.spatial_vector(f,wp.cross(r,f)))

@wp.kernel
def subtract_force(dt:float,q:wp.array[wp.transform],qd:wp.array[wp.spatial_vector],f:wp.array[wp.spatial_vector],ii:wp.array[wp.mat33],im:wp.array[float],oq:wp.array[wp.transform],ov:wp.array[wp.spatial_vector]):
    b=wp.tid();rot=wp.transform_get_rotation(q[b])
    dv=dt*im[b]*wp.spatial_top(f[b]);dw=dt*wp.quat_rotate(rot,ii[b]*wp.quat_rotate_inv(rot,wp.spatial_bottom(f[b])))
    oq[b]=q[b];ov[b]=qd[b]-wp.spatial_vector(dv,dw)

@wp.kernel
def rheology(h:wp.array[float],eta:wp.array[float],tf:wp.array[float]):
    i=wp.tid();t=temperature(h[i]);tf[i]=t
    # Crystal-bearing melt viscosity, not an elastic skin standing in for rock.
    eta[i]=wp.pow(10.0,-4.55+5978.4/(wp.max(t,1300.0)-595.3))*8.0

def clip(poly,n,b):
    out=[]
    for a,c in zip(poly,np.roll(poly,-1,axis=0)):
        da=np.dot(n,a)-b;dc=np.dot(n,c)-b
        if da<=0:out.append(a)
        if (da<0)!=(dc<0):out.append(a+(c-a)*da/(da-dc))
    return np.array(out)

def initial(pitch):
    rng=np.random.default_rng(29031)
    # Deliberately non-uniform plate sizes: a few broad plates, many small ones.
    seeds=[]
    for _ in range(5000):
        xy=rng.uniform([-.215,-.12],[.215,.12])
        if (xy[0]/.215)**2+(xy[1]/.12)**2>.92:continue
        spacing=.033 if xy[0]>.03 else .052
        if all(np.linalg.norm(xy-s)>spacing for s in seeds):seeds.append(xy)
        if len(seeds)>=39:break
    seeds=np.array(seeds);rocks=[]
    for i,s in enumerate(seeds):
        poly=np.array([[-.225,-.13],[.225,-.13],[.225,.13],[-.225,.13]])
        for j,o in enumerate(seeds):
            if i!=j:poly=clip(poly,o-s,(np.dot(o,o)-np.dot(s,s))/2)
        poly=s+(poly-s)*rng.uniform(.79,.94)
        # Clip the front to the same finite elliptical flow footprint.
        for angle in np.linspace(0,2*np.pi,40,endpoint=False):
            n=np.array([np.cos(angle)/.219,np.sin(angle)/.125]);poly=clip(poly,n,1.)
            if len(poly)<3:break
        if len(poly)<3:continue
        c=poly.mean(0);thick=rng.uniform(.015,.034)
        radial=(c[0]/.22)**2+(c[1]/.125)**2
        base=max(.006,.006+.045*np.sqrt(max(0.,1-radial))-.011)+rng.uniform(-.003,.003)
        # Three unequal rings give chipped shoulders rather than box prisms.
        vv=[]
        for scale,z in [(.80,base),(1.,base+thick*.36),(.75,base+thick)]:
            ring=c+(poly-c)*scale
            for xy in ring:vv.append([*xy,z+rng.uniform(-.004,.004)])
        vv=np.array(vv);hull=ConvexHull(vv);ff=hull.simplices.copy()
        normals=np.cross(vv[ff[:,1]]-vv[ff[:,0]],vv[ff[:,2]]-vv[ff[:,0]])
        swap=np.sum(normals*hull.equations[:,:3],axis=1)<0
        ff[swap]=ff[swap][:,[0,2,1]]
        origin=vv.mean(0);rocks.append(dict(v=vv-origin,f=ff,q=np.r_[origin,[0,0,0,1]],equations=hull.equations))
    axes=[np.arange(-.22+pitch/2,.22,pitch),np.arange(-.125+pitch/2,.125,pitch),np.arange(pitch/2,.05,pitch)]
    x=np.array(np.meshgrid(*axes,indexing='ij')).reshape(3,-1).T
    radial=(x[:,0]/.22)**2+(x[:,1]/.125)**2
    inside=(radial<1)&(x[:,2]<.006+.045*np.sqrt(np.maximum(0,1-radial)))
    x=x[inside]
    for r in rocks:
        eq=r['equations'];inside=np.max(x@eq[:,:3].T+eq[:,3],axis=1)<pitch*.2
        x=x[~inside]
    return x.astype('f4'),rocks

def run(name,pitch,until,wall,basis):
    folder=ROOT/name;folder.mkdir(parents=True,exist_ok=True);wp.init()
    with wp.ScopedDevice('cuda:0'):
        x,rocks=initial(pitch);n=len(x);nb=len(rocks);gravity=(2.3,0.,-9.54)
        rb=newton.ModelBuilder(gravity=gravity);rb.rigid_gap=.001
        for i,r in enumerate(rocks):
            b=rb.add_body(xform=wp.transform(r['q'][:3],r['q'][3:]),label=f'basalt-{i}')
            mesh=newton.Mesh(vertices=r['v'].astype('f4'),indices=r['f'].ravel().astype('i4'))
            rb.add_shape_convex_hull(b,mesh=mesh,cfg=newton.ModelBuilder.ShapeConfig(density=2450.,mu=.65,gap=.0008))
        rb.add_ground_plane(cfg=newton.ModelBuilder.ShapeConfig(mu=.65,gap=.0008))
        rigid=rb.finalize();ra=rigid.state();rbstate=rigid.state();control=rigid.control()
        newton.eval_fk(rigid,rigid.joint_q,rigid.joint_qd,ra)
        rs=SolverXPBD(rigid,iterations=10,rigid_contact_con_weighting=False)
        collision=newton.CollisionPipeline(rigid);contacts=collision.contacts()
        pb=newton.ModelBuilder(gravity=gravity);SolverImplicitMPM.register_custom_attributes(pb)
        vel=np.zeros_like(x);vel[:,0]=.045
        pb.add_particles(pos=x,vel=vel,mass=np.full(n,2700*pitch**3),radius=np.full(n,pitch/2))
        model=pb.finalize();model.mpm.young_modulus.fill_(1.2e9);model.mpm.poisson_ratio.fill_(.49)
        model.mpm.viscosity.fill_(800.);model.mpm.friction.fill_(0.);model.mpm.yield_stress.fill_(0.);model.mpm.tensile_yield_ratio.fill_(0.)
        fluid=model.state();fluid.body_q=wp.clone(ra.body_q);fluid.body_qd=wp.clone(ra.body_qd);fluid.body_f=wp.zeros_like(ra.body_f)
        solver=SolverImplicitMPM(model,SolverImplicitMPM.Config(voxel_size=2*pitch,velocity_basis=basis,grid_type='sparse',air_drag=.001,tolerance=1e-5,max_iterations=250))
        solver.setup_collider(model=rigid)
        applied=wp.zeros_like(ra.body_f);imp=pos=ids=None
        h=wp.full(n,732220.,dtype=float);hn=wp.empty_like(h);tf=wp.empty_like(h)
        grid=wp.HashGrid(128,64,64);area=wp.zeros(n);loss=wp.zeros(n);cond=wp.zeros(n)
        geometry={}
        for i,r in enumerate(rocks):geometry[f'v{i}']=r['v'];geometry[f'f{i}']=r['f']
        np.savez_compressed(folder/'rocks.npz',**geometry,initial_q=np.array([r['q'] for r in rocks]),mass=rigid.body_mass.numpy())
        start=time.monotonic();clock=0.;rows=[];step=0;initialmass=n*2700*pitch**3;lossj=0.
        def save():
            wp.launch(rheology,n,inputs=[h,model.mpm.viscosity,tf])
            xx=fluid.particle_q.numpy();vv=fluid.particle_qd.numpy();q=ra.body_q.numpy();qd=ra.body_qd.numpy()
            if not all(np.isfinite(a).all() for a in [xx,vv,q,qd,h.numpy()]):raise RuntimeError('Nonfinite state rejected')
            extra={field:getattr(fluid.mpm,field).numpy() for field in ('particle_qd_grad','particle_elastic_strain','particle_Jp','particle_stress','particle_transform')}
            np.savez_compressed(folder/f'frame-{round(clock*1000):06d}.npz',x=xx,v=vv,rest=x,h=h.numpy(),temperature=tf.numpy(),body_q=q,body_qd=qd,pitch=pitch,time=clock,**extra)
            row=dict(time=clock,maximumFluidSpeed=float(np.linalg.norm(vv,axis=1).max()),maximumBodySpeed=float(np.linalg.norm(qd[:,:3],axis=1).max()),minimumBodyHeight=float(q[:,2].min()),fluidHeightRange=[float(xx[:,2].min()),float(xx[:,2].max())],thermalLossJ=lossj,wallSeconds=time.monotonic()-start)
            rows.append(row);print(json.dumps(row),flush=True)
        save()
        while clock<until-1e-8:
            if time.monotonic()-start>wall:break
            dt=min(.005,until-clock)
            for sub in range(4):
                ra.clear_forces()
                if ids is not None:wp.launch(body_forces,len(ids),inputs=[dt,ids,imp,pos,solver.collider_body_index,ra.body_q,rigid.body_com,ra.body_f])
                applied.assign(ra.body_f);collision.collide(ra,contacts);rs.step(ra,rbstate,control,contacts,dt/4);ra,rbstate=rbstate,ra
            wp.launch(subtract_force,nb,inputs=[dt,ra.body_q,ra.body_qd,applied,rigid.body_inv_inertia,rigid.body_inv_mass,fluid.body_q,fluid.body_qd])
            grid.build(fluid.particle_q,2.6*pitch)
            wp.launch(heat_step,n,inputs=[fluid.particle_q,h,hn,grid.id,pitch,1.6,.94,12.,293.15,1173.15,dt,1,area,loss,cond])
            h,hn=hn,h;wp.launch(rheology,n,inputs=[h,model.mpm.viscosity,tf]);solver.step(fluid,fluid,None,None,dt)
            imp,pos,ids=solver.collect_collider_impulses(fluid)
            clock+=dt;step+=1;lossj+=float(loss.numpy().sum(dtype='f8'))
            if step%20==0 or clock>=until-1e-8:save()
        report=dict(status='complete' if clock>=until-1e-8 else 'bounded-preview',time=clock,particles=n,rocks=nb,pitch=pitch,velocityBasis=basis,fluidMassKg=initialmass,bodyMassKg=float(rigid.body_mass.numpy().sum()),rows=rows,seconds=time.monotonic()-start,sourceSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),method='Newton implicit viscous MPM, XPBD rigid contact, native bidirectional collider impulses, particle enthalpy conduction/radiation.',limitations='Pre-existing basalt geometry and initial thermal state are authored. No new fracture formation, melting of rigid bodies, rock-fluid heat exchange or smoke solver. Finite release; nominal constitutive values; no convergence claim.')
        (folder/'receipt.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ['status','time','particles','rocks','seconds']}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='clinker');p.add_argument('--pitch',type=float,default=.004);p.add_argument('--until',type=float,default=.6);p.add_argument('--wall',type=float,default=150);p.add_argument('--basis',default='B2');a=p.parse_args();run(a.name,a.pitch,a.until,a.wall,a.basis)
