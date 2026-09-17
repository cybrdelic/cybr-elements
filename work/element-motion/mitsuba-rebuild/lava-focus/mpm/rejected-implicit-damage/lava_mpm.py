"""Three-dimensional implicit thermoviscoelastic APIC/MPM on the CPU.

SI units. No imported geometry, artificial heat sink, gravity schedule, shape
attractor, or animated material stages. Constitutive and discretization limits
are recorded with the cache; this is not claimed to reproduce a production
solver merely by using MPM. Fracture energy, thermal contraction, latent heat,
viscous relaxation, and regularized tensile damage have explicit state.
"""
from pathlib import Path
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='2', NUMBA_NUM_THREADS='2')
from dataclasses import dataclass, asdict
import json, time
import numpy as np
from numba import njit
from scipy.sparse import coo_matrix, diags, vstack, csr_matrix
from scipy.sparse.linalg import spsolve
from lava_mpm_fracture import Connectivity,mechanical_fields,contact_fields,contact_matrix,implicit_contact,viscous_interfaces,local_fracture_labels

ROOT = Path(__file__).resolve().parent / 'lava-focus' / 'mpm'
SQ2 = np.sqrt(2.)


@dataclass
class Material:
    density: float = 2700.
    cp: float = 1200.
    solidus: float = 1173.15
    liquidus: float = 1423.15
    latent_heat: float = 400000.
    conductivity: float = 1.6
    emissivity: float = .94
    convection: float = 12.
    ambient: float = 293.15
    young: float = 30.e9
    poisson: float = .25
    liquid_bulk: float = 20.e9
    expansion: float = 8.e-6
    tensile_strength: float = 8.e6
    fracture_energy: float = 100.
    viscosity_reference: float = 150.
    viscosity_temperature: float = 1450.
    activation_over_R: float = 60000.
    friction: float = .6
    crystal_lock_fraction: float = .65

    def enthalpy(self, t):
        t = np.asarray(t)
        return self.cp * (t - self.solidus) + self.latent_heat * np.clip((t-self.solidus)/(self.liquidus-self.solidus), 0, 1)

    def temperature(self, h):
        h = np.asarray(h)
        interval = self.cp*(self.liquidus-self.solidus)+self.latent_heat
        return np.where(h < 0, self.solidus+h/self.cp,
                        np.where(h <= interval, self.solidus+h/(self.cp+self.latent_heat/(self.liquidus-self.solidus)),
                                 self.liquidus+(h-interval)/self.cp))

    def capacity(self, t):
        return self.cp + self.latent_heat/(self.liquidus-self.solidus) * ((t >= self.solidus) & (t <= self.liquidus))

    def solid(self, t):
        return np.clip((self.liquidus-t)/(self.liquidus-self.solidus), 0, 1)

    def viscosity(self, t):
        # Arrhenius extrapolation is a declared nominal constitutive law,
        # not a fitted composition-specific rheology or a capped CPU trick.
        return self.viscosity_reference*np.exp(self.activation_over_R*(1/t-1/self.viscosity_temperature))

    def network(self, t, dt):
        """Crystal suspension below packing; elastic skeleton above packing.

        The old model used melt viscosity for the basalt skeleton. At 1200 K
        this erased solid shear stress in about 0.1 ms. Crystal packing is a
        separate state transition: the Krieger-Dougherty fluidity tends to
        zero at the declared packing fraction. No huge viscosity cap is
        needed to represent its elastic limit. Packing is nominal, not a
        composition-calibrated crystallization or creep law.
        """
        solid = self.solid(t)
        eta = self.viscosity(t)
        mu = self.young / (2*(1+self.poisson)) * solid**3
        fluidity = np.maximum(1-solid/self.crystal_lock_fraction, 0)**(2.5*self.crystal_lock_fraction)/eta
        relaxation = 1/(1+dt*mu*fluidity)
        return mu, fluidity, relaxation, dt*mu*relaxation


@njit(cache=True)
def basis(x, dx, origin, shape):
    n = len(x)
    ids = np.empty((n, 27), np.int64)
    w = np.empty((n, 27))
    grad = np.empty((n, 27, 3))
    dp = np.empty((n, 27, 3))
    for p in range(n):
        q = (x[p]-origin)/dx
        b = np.floor(q-.5).astype(np.int64)
        f = q-b
        ww = np.empty((3, 3)); gg = np.empty((3, 3))
        for c in range(3):
            ww[0,c] = .5*(1.5-f[c])**2; ww[1,c] = .75-(f[c]-1)**2; ww[2,c] = .5*(f[c]-.5)**2
            gg[0,c] = (f[c]-1.5)/dx; gg[1,c] = -2*(f[c]-1)/dx; gg[2,c] = (f[c]-.5)/dx
        at = 0
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    a,b1,c = b[0]+i,b[1]+j,b[2]+k
                    if min(a,b1,c) < 0 or a >= shape[0] or b1 >= shape[1] or c >= shape[2]:
                        raise ValueError('Particle kernel left the domain; no silent particle clipping')
                    ids[p,at] = (a*shape[1]+b1)*shape[2]+c
                    w[p,at] = ww[i,0]*ww[j,1]*ww[k,2]
                    grad[p,at,0] = gg[i,0]*ww[j,1]*ww[k,2]
                    grad[p,at,1] = ww[i,0]*gg[j,1]*ww[k,2]
                    grad[p,at,2] = ww[i,0]*ww[j,1]*gg[k,2]
                    dp[p,at] = (np.array([i,j,k])-f)*dx
                    at += 1
    return ids, w, grad, dp


@njit(cache=True)
def p2g(ids, w, dp, mass, v, C, h, nodes):
    gm = np.zeros(nodes); momentum = np.zeros((nodes,3)); energy = np.zeros(nodes)
    for p in range(len(ids)):
        for k in range(27):
            i = ids[p,k]; mw = mass[p]*w[p,k]
            gm[i] += mw; energy[i] += mw*h[p]
            momentum[i] += mw*(v[p]+C[p]@dp[p,k])
    return gm, momentum, energy


@njit(cache=True)
def basis_rect(x,cell,origin,shape):
    n=len(x);ids=np.empty((n,27),np.int64);w=np.empty((n,27));grad=np.empty((n,27,3));dp=np.empty((n,27,3))
    for p in range(n):
        q=(x[p]-origin)/cell;b=np.floor(q-.5).astype(np.int64);f=q-b;ww=np.empty((3,3));gg=np.empty((3,3))
        for c in range(3):
            ww[0,c]=.5*(1.5-f[c])**2;ww[1,c]=.75-(f[c]-1)**2;ww[2,c]=.5*(f[c]-.5)**2
            gg[0,c]=(f[c]-1.5)/cell[c];gg[1,c]=-2*(f[c]-1)/cell[c];gg[2,c]=(f[c]-.5)/cell[c]
        at=0
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    a=b[0]+i;bb=b[1]+j;c=b[2]+k
                    if min(a,bb,c)<0 or a>=shape[0] or bb>=shape[1] or c>=shape[2]:raise ValueError('Particle kernel left the rectangular domain')
                    ids[p,at]=(a*shape[1]+bb)*shape[2]+c;w[p,at]=ww[i,0]*ww[j,1]*ww[k,2]
                    grad[p,at,0]=gg[i,0]*ww[j,1]*ww[k,2];grad[p,at,1]=ww[i,0]*gg[j,1]*ww[k,2];grad[p,at,2]=ww[i,0]*ww[j,1]*gg[k,2]
                    dp[p,at]=(np.array([i,j,k])-f)*cell;at+=1
    return ids,w,grad,dp


def strain_matrix(ids, grad, nodes):
    """Mandel symmetric strain, particle-major six-component rows."""
    n = len(ids); pr = np.broadcast_to(np.arange(n)[:,None]*6, ids.shape)
    rows=[]; cols=[]; data=[]
    for axis in range(3):
        rows.append((pr+axis).ravel()); cols.append((ids*3+axis).ravel()); data.append(grad[:,:,axis].ravel())
    for row,(i,j) in enumerate(((1,2),(0,2),(0,1)),3):
        for a,b in ((i,j),(j,i)):
            rows.append((pr+row).ravel()); cols.append((ids*3+a).ravel()); data.append((grad[:,:,b]/SQ2).ravel())
    B = coo_matrix((np.concatenate(data),(np.concatenate(rows),np.concatenate(cols))),shape=(n*6,nodes*3)).tocsr()
    D = B[0::6]+B[1::6]+B[2::6]
    T = np.eye(6); T[:3,:3] -= 1/3
    rr=[]; cc=[]; dd=[]
    for i in range(6):
        for j in range(6):
            if T[i,j]:
                rr.append(np.arange(n)*6+i); cc.append(np.arange(n)*6+j); dd.append(np.full(n,T[i,j]))
    dev = coo_matrix((np.concatenate(dd),(np.concatenate(rr),np.concatenate(cc))),shape=(n*6,n*6)).tocsr()
    return B, dev@B, D


def tensor(m):
    t=np.zeros((len(m),3,3)); t[:,0,0]=m[:,0]; t[:,1,1]=m[:,1]; t[:,2,2]=m[:,2]
    t[:,1,2]=t[:,2,1]=m[:,3]/SQ2; t[:,0,2]=t[:,2,0]=m[:,4]/SQ2; t[:,0,1]=t[:,1,0]=m[:,5]/SQ2
    return t


def mandel(t):
    return np.c_[t[:,0,0],t[:,1,1],t[:,2,2],t[:,1,2]*SQ2,t[:,0,2]*SQ2,t[:,0,1]*SQ2]


def laplacian(shape, occupied, fill, dx, conductivity,cell_size=None):
    index=np.arange(np.prod(shape)).reshape(shape); rows=[];cols=[];data=[]
    for axis in range(3):
        sa=[slice(None)]*3;sb=sa.copy();sa[axis]=slice(None,-1);sb[axis]=slice(1,None)
        a=index[tuple(sa)].ravel();b=index[tuple(sb)].ravel()
        keep=occupied[a]&occupied[b];a=a[keep];b=b[keep]
        # Harmonic occupancy scales the conducting cross-sectional area.
        coefficient=dx if cell_size is None else np.prod(cell_size)/cell_size[axis]**2
        q=conductivity*coefficient*2*fill[a]*fill[b]/np.maximum(fill[a]+fill[b],1e-30)
        rows.extend([a,a,b,b]);cols.extend([a,b,a,b]);data.extend([q,-q,-q,q])
    return coo_matrix((np.concatenate(data),(np.concatenate(rows),np.concatenate(cols))),shape=(len(occupied),)*2).tocsr()


def heat_solve(material, h0, mass, K, area, gas_temperature, dt, bed_area=None, bed_conductance=0., bed_temperature=293.15):
    """Nonlinear backward Euler enthalpy solve. All boundary losses metered."""
    t0=material.temperature(h0); t=t0.copy(); ba=np.zeros_like(area) if bed_area is None else bed_area
    sigma=5.670374419e-8; residual0=None
    for it in range(35):
        radiation=material.emissivity*sigma*area*(t**4-material.ambient**4)
        convection=material.convection*area*(t-gas_temperature)
        bed=bed_conductance*ba*(t-bed_temperature)
        residual=mass*(material.enthalpy(t)-h0)+dt*(K@t+radiation+convection+bed)
        norm=float(np.linalg.norm(residual)); residual0=norm if residual0 is None else residual0
        if norm <= 1e-9*max(residual0,1): break
        diagonal=mass*material.capacity(t)+dt*(4*material.emissivity*sigma*area*t**3+material.convection*area+bed_conductance*ba)
        delta=spsolve(diags(diagonal)+dt*K,-residual)
        # Enthalpy has two derivative discontinuities; backtrack the actual
        # nonlinear residual rather than averaging temperatures across phases.
        step=1.
        for _ in range(14):
            trial=t+step*delta
            rr=mass*(material.enthalpy(trial)-h0)+dt*(K@trial+material.emissivity*sigma*area*(trial**4-material.ambient**4)+material.convection*area*(trial-gas_temperature)+bed_conductance*ba*(trial-bed_temperature))
            if np.all(trial>1) and np.linalg.norm(rr)<norm: break
            step*=.5
        t=trial
    else: raise RuntimeError('Nonlinear heat solve failed; cache not advanced')
    hn=material.enthalpy(t)
    radiation=material.emissivity*sigma*area*(t**4-material.ambient**4)*dt
    convection=material.convection*area*(t-gas_temperature)*dt
    bed=bed_conductance*ba*(t-bed_temperature)*dt
    balance=float(np.dot(mass,hn-h0)+np.sum(radiation+convection+bed))
    return hn,dict(radiation=radiation,convection=convection,bed=bed,balance=balance,iterations=it+1)


def tensile_damage(strain_history, damage, principal_stress, young, strength, gc, length):
    """Exponential crack-band softening; integral sigma d(opening) = Gc.

    The finite grid resolves a damage band, not a discontinuous zero-width
    crack. This law does not claim a mixed-mode basalt fracture calibration.
    """
    e0=strength/young
    ef=gc/(strength*length)-e0/2
    if np.any(ef<=0):raise ValueError('Grid is too coarse to resolve the specified fracture energy and tensile strength')
    history=np.maximum(strain_history,np.maximum(principal_stress,0)/young)
    ratio=np.divide(e0,history,out=np.ones_like(history),where=history>0)
    d=np.where(history>e0,1-ratio*np.exp(-(history-e0)/ef),0)
    return history,np.maximum(damage,np.clip(d,0,1))


def ground_map(xyz,dx,labels=None,ground_mask=None,cell_size=None):
    """Odd ghost extension at the z=0 no-slip substrate.

    Setting just the z=0 grid velocity to zero does not enforce a quadratic
    B-spline boundary. Mirroring the support enforces zero interpolated flux.
    """
    cell=np.full(3,dx) if cell_size is None else np.asarray(cell_size);hz=cell[2]
    grounded=np.ones(len(xyz),bool) if ground_mask is None else np.asarray(ground_mask,dtype=bool)
    fixed=np.zeros(len(xyz)*3,dtype=bool)
    fixed[np.flatnonzero((xyz[:,2]<hz*1e-7)&grounded)[:,None]*3+np.arange(3)]=True
    free=np.flatnonzero(~fixed);unknown=np.full(len(fixed),-1,dtype=int);unknown[free]=np.arange(len(free))
    labels=np.zeros(len(xyz),dtype=int) if labels is None else labels
    lookup={(*np.round(q/cell).astype(int),int(labels[i])):i for i,q in enumerate(xyz)}
    rr=list(free);cc=list(range(len(free)));dd=[1.]*len(free)
    for i in np.flatnonzero((xyz[:,2]<-hz*1e-7)&grounded):
        q=xyz[i].copy();q[2]*=-1;j=lookup.get((*np.round(q/cell).astype(int),int(labels[i])))
        if j is None:raise RuntimeError('Missing reflected ground node')
        for c in range(3):
            u=unknown[j*3+c]
            if u>=0:rr.append(i*3+c);cc.append(int(u));dd.append(-1.)
    return coo_matrix((dd,(rr,cc)),shape=(len(fixed),len(free))).tocsr()


class MPM:
    def __init__(self, x, spacing, dx, temperature=1450., material=None, origin=None, shape=None, gravity=(0,0,-9.81), ground=True,cell_size=None,sample_size=None,contact_solver='dense',bonded_bed=False,coherent_fraction=None,failure_fraction=None):
        self.material=material or Material(); self.dx=float(dx); self.spacing=float(spacing)
        self.cell_size=np.full(3,self.dx) if cell_size is None else np.array(cell_size,dtype=float)
        self.sample_size=np.full(3,self.spacing) if sample_size is None else np.array(sample_size,dtype=float)
        self.rectangular=bool(np.ptp(self.cell_size)>0)
        self.contact_solver=contact_solver
        self.bonded_bed=bool(bonded_bed)
        self.coherent_fraction=self.material.crystal_lock_fraction if coherent_fraction is None else float(coherent_fraction)
        self.failure_fraction=self.coherent_fraction if failure_fraction is None else float(failure_fraction)
        self.origin=np.array(origin if origin is not None else [-.15,-.15,-.04],dtype=float)
        self.shape=tuple(int(q) for q in (shape if shape is not None else [40,30,30])); self.gravity=np.array(gravity,dtype=float);self.ground=ground
        self.x=np.array(x,dtype=float); self.rest=self.x.copy();n=len(x)
        self.v=np.zeros((n,3));self.C=np.zeros((n,3,3));self.F=np.tile(np.eye(3),(n,1,1))
        self.mass=np.full(n,self.material.density*np.prod(self.sample_size));self.volume=np.full(n,np.prod(self.sample_size))
        self.h=np.broadcast_to(self.material.enthalpy(temperature),(n,)).copy()
        self.deviator=np.zeros((n,6));self.dilation=np.zeros(n);self.damage=np.zeros(n);self.history=np.zeros(n);self.thermal_volume=np.zeros(n)
        self.principal_direction=np.tile([0.,0.,1.],(n,1));self.connectivity=Connectivity(n)
        self.time=0.;self.initial_energy=float(self.mass@self.h);self.initial_mass=float(self.mass.sum())
        self.ledger=dict(radiation=0.,convection=0.,bed=0.,viscous_heat=0.,fracture=0.,pressure_cavitation=0.,ground_impulse=0.,ground_dissipation=0.,contact_heat=0.)
        self.rows=[];self.last_surface=None;self.last_grid=None

    def add_particles(self,x,velocity,temperature,volume,source_kind='inlet'):
        """Account for a physical source; never silently add matter/energy."""
        x=np.asarray(x,dtype=float);n=len(x);volume=np.asarray(volume,dtype=float)
        velocity=np.asarray(velocity,dtype=float);temperature=np.asarray(temperature,dtype=float)
        if x.shape!=(n,3) or velocity.shape!=(n,3) or volume.shape!=(n,) or temperature.shape!=(n,):raise ValueError('Invalid source quadrature shapes')
        if not all(np.isfinite(q).all() for q in (x,velocity,temperature,volume)) or np.any(volume<=0) or np.any(temperature<=0):raise ValueError('Invalid source state')
        basis_rect(x,self.cell_size,self.origin,np.array(self.shape))
        mass=volume*self.material.density;h=self.material.enthalpy(temperature)
        values=dict(x=x,rest=x.copy(),v=velocity,C=np.zeros((n,3,3)),F=np.tile(np.eye(3),(n,1,1)),mass=mass,volume=volume,h=h,
                    deviator=np.zeros((n,6)),dilation=np.zeros(n),damage=np.zeros(n),history=np.zeros(n),thermal_volume=np.zeros(n),principal_direction=np.tile([0.,0.,1.],(n,1)))
        for key,value in values.items():setattr(self,key,np.concatenate([getattr(self,key),value]))
        self.connectivity.frozen=np.r_[self.connectivity.frozen,np.zeros(n,dtype=bool)]
        self.connectivity.labels=np.r_[self.connectivity.labels,np.zeros(n,dtype=int)]
        for key,value in [('source_mass',mass.sum()),('source_enthalpy',mass@h),('source_kinetic',.5*np.sum(mass*np.sum(velocity*velocity,axis=1)))]:
            self.ledger[key]=self.ledger.get(key,0.)+float(value)
        self.ledger[source_kind+'_particles']=self.ledger.get(source_kind+'_particles',0)+n

    def step(self,dt,thermal=True,mechanics=True,gas=None,bed=None,boundary=None,node_velocity=None,damage_iterate=None):
        start=time.time();m=self.material;n=len(self.x);nodes=int(np.prod(self.shape));dx=self.dx
        cell_size=self.cell_size;cell_volume=np.prod(cell_size);hz=cell_size[2]
        ids,w,grad,dp=basis_rect(self.x,cell_size,self.origin,np.array(self.shape)) if self.rectangular else basis(self.x,dx,self.origin,np.array(self.shape))
        gm,momentum,energy=p2g(ids,w,dp,self.mass,self.v,self.C,self.h,nodes)
        active=gm>self.mass.mean()*1e-11
        # Every referenced node is retained, avoiding a mass threshold leak.
        active[np.unique(ids)]=True
        ai=np.flatnonzero(active);inverse=np.full(nodes,-1,dtype=int);inverse[ai]=np.arange(len(ai));local=inverse[ids]
        ma=gm[ai];safe=np.maximum(ma,self.mass.mean()*1e-16)
        gv=momentum[ai]/safe[:,None];ha=energy[ai]/safe
        xyz=self.origin+np.array(np.unravel_index(ai,self.shape)).T*cell_size
        phi=gm/(m.density*cell_volume)
        gradients=np.array(np.gradient(phi.reshape(self.shape),*cell_size)).reshape(3,-1).T
        area=np.linalg.norm(gradients[ai],axis=1)*cell_volume
        normal=-gradients[ai]/np.maximum(np.linalg.norm(gradients[ai],axis=1)[:,None],1e-30)
        bottom=area*np.clip(-normal[:,2],0,1)*(xyz[:,2]<hz*.8) if self.ground else np.zeros_like(area)
        exposed=np.maximum(0,area-bottom)
        previous_t=m.temperature(self.h)
        thermal_error=0.;heat_iters=0;viscous_j=0.;fracture_j=0.;mechanical_residual=0.
        if thermal:
            K=laplacian(self.shape,active,phi,dx,m.conductivity,cell_size)[ai][:,ai]
            tg=np.full(len(ai),m.ambient) if gas is None else gas.temperature_at(xyz+normal*cell_size)
            bed_temperature=m.ambient if bed is None else bed.temperature_at(xyz)
            bed_conductance=m.conductivity/(hz*.5) if bed is None else bed.conductance(hz,m.conductivity)
            hn,heat=heat_solve(m,ha,safe,K,exposed,tg,dt,bottom,bed_conductance,bed_temperature)
            self.h+=np.sum(w*(hn-ha)[local],axis=1)
            for key in ('radiation','convection','bed'):self.ledger[key]+=float(heat[key].sum())
            thermal_error=heat['balance'];heat_iters=heat['iterations']
            if gas is not None:gas.add_surface_heat(xyz+normal*cell_size,heat['convection'])
            if bed is not None:bed.add_heat(xyz,heat['bed'])
        temperature=m.temperature(self.h);solid=m.solid(temperature)
        self.last_surface=(xyz,normal,exposed,temperature if len(temperature)==len(xyz) else m.temperature(ha))
        contact_count=0;contact_error=0.;split_nodes=0
        if mechanics:
            constitutive_damage=self.damage if damage_iterate is None else np.maximum(self.damage,np.asarray(damage_iterate))
            labels=self.connectivity.update(self.x,solid,constitutive_damage,self.principal_direction,self.sample_size,self.coherent_fraction)
            tags=local_fracture_labels(ids,self.connectivity,self.shape,self.origin,hz,self.ground,cell_size,None if boundary is None else boundary['plane']) if self.connectivity.broken.any() else np.broadcast_to(labels[:,None],ids.shape)
            grid_ids,field_ids,local=mechanical_fields(ids,tags)
            _,node_counts=np.unique(grid_ids,return_counts=True);split_nodes=int((node_counts>1).sum())
            thermal_node=inverse[grid_ids]
            field_m,field_momentum,_=p2g(local,w,dp,self.mass,self.v,self.C,self.h,len(grid_ids))
            fraction=field_m/np.maximum(gm[grid_ids],1e-30)
            exposed=exposed[thermal_node]*fraction;normal=normal[thermal_node];xyz=xyz[thermal_node]
            ma=field_m;safe=np.maximum(ma,self.mass.mean()*1e-16);gv=field_momentum/safe[:,None]
            B,Bdev,D=strain_matrix(local,grad,len(grid_ids))
            # Cell-averaged dilation avoids particle-wise volumetric locking.
            cell=np.floor((self.x-self.origin)/cell_size).astype(int)
            cell_grid=np.ravel_multi_index(cell.T,self.shape)
            pressure_labels=tags[np.arange(n),(ids==cell_grid[:,None]).argmax(1)]
            _,ci=np.unique(np.c_[cell,pressure_labels],axis=0,return_inverse=True);nc=int(ci.max()+1)
            cv=np.bincount(ci,weights=self.volume,minlength=nc)
            W=coo_matrix((self.volume/cv[ci],(ci,np.arange(n))),shape=(nc,n)).tocsr();P=W@D
            eta=m.viscosity(temperature)
            shear,network_fluidity,relax,network_viscosity=m.network(temperature,dt)
            # Newtonian melt and a crystallizing Maxwell network act in
            # parallel. Only the network stores elastic stress between steps;
            # carrying viscous stress as elastic history causes false recoil.
            solvent_viscosity=eta*(1-solid)**2
            surviving=np.maximum(1-constitutive_damage,1e-8)
            # Fracture breaks the load-bearing network; it does not remove
            # the Newtonian liquid between crystals. Scaling both branches
            # by damage turned hot broken crust into nearly inviscid debris.
            effective_viscosity=solvent_viscosity+network_viscosity*surviving
            olddev=self.deviator*relax[:,None]*(solid>0)[:,None]
            if damage_iterate is not None:
                olddev*= (surviving/np.maximum(1-self.damage,1e-8))[:,None]
            thermal_dilation=3*m.expansion*(temperature-previous_t)
            self.thermal_volume+=thermal_dilation
            strain0=self.dilation-thermal_dilation
            # Compression remains supported by the melt. Hydrostatic
            # tension is carried by the surviving crystal skeleton. The
            # former 95% damage cutoff erased tensile strain before the
            # 99.5% bond-release criterion could ever be reached.
            can_tension=solid>self.failure_fraction
            tension_branch=can_tension&(strain0>0)
            bulk=m.liquid_bulk*np.where(tension_branch,surviving,1.)
            p0=bulk*strain0
            # Liquid and fully damaged material cannot sustain hydrostatic
            # tension. Intact solid retains tension for thermal fracture.
            p0=np.where(can_tension,p0,np.minimum(p0,0))
            olddev_flat=(olddev*self.volume[:,None]).ravel()
            viscdiag=np.repeat(2*dt*effective_viscosity*self.volume,6)
            kcell=np.asarray(W@bulk).ravel()
            pcell=np.asarray(W@p0).ravel()
            A=diags(np.repeat(safe,3))+Bdev.T@diags(viscdiag)@Bdev+dt**2*P.T@diags(cv*kcell)@P
            phase_mass=np.bincount(local.ravel(),weights=(self.mass[:,None]*w*(~self.connectivity.frozen)[:,None]).ravel(),minlength=len(grid_ids))
            eta_mass=np.bincount(local.ravel(),weights=(self.mass[:,None]*w*eta[:,None]).ravel(),minlength=len(grid_ids))
            field_gradient=np.zeros((len(ma),3))
            for axis in range(3):np.add.at(field_gradient[:,axis],local.ravel(),(self.mass[:,None]*grad[:,:,axis]).ravel())
            interfaceA,interface_pairs,interface_coeff=viscous_interfaces(grid_ids,ma,phase_mass>ma*.5,eta_mass/safe,dx,m.density,dt,cell_size,field_gradient)
            A=A+interfaceA
            rhs=(ma[:,None]*(gv+dt*self.gravity)).ravel()-dt*(Bdev.T@olddev_flat+P.T@(cv*pcell))
            if gas is not None:
                # Dynamic gas pressure reacts on the same material surface
                # that releases heat; atmospheric pressure cancels in gauge.
                gas_pressure=gas.pressure_at(xyz+normal*cell_size)
                rhs+=(-dt*gas_pressure[:,None]*normal*exposed[:,None]).ravel()
            lift=np.zeros(len(grid_ids)*3)
            grounded=phase_mass>ma*.5
            if self.bonded_bed and self.ground:
                # Declared perfect-wetting/no-slip substrate: only frozen
                # domains actually touching it retain the liquid's bond.
                # A hovering solid with an overlapping stencil stays free.
                radius=.5*self.sample_size[2]*np.cbrt(self.volume/np.prod(self.sample_size))
                attached=self.connectivity.frozen&(self.x[:,2]-radius<hz*.05)
                attached_mass=np.bincount(local.ravel(),weights=(self.mass[:,None]*w*attached[:,None]).ravel(),minlength=len(grid_ids))
                grounded|=attached_mass>ma*1e-6
            if boundary is not None:
                from lava_mpm_inlet import velocity_map
                S,lift=velocity_map(xyz,dx,field_ids,boundary,self.ground,grounded,cell_size)
            else:S=ground_map(xyz,dx,field_ids,grounded,cell_size) if self.ground else diags(np.ones(len(grid_ids)*3),format='csr')
            if node_velocity is not None:
                from lava_mpm_loading import prescribe
                prescribed_mask,prescribed_values=node_velocity(xyz)
                S,lift=prescribe(S,lift,prescribed_mask,prescribed_values)
            original_rhs=rhs.copy();rhs=rhs-A@lift
            reducedA=S.T@A@S;reducedrhs=S.T@rhs
            wallC=csr_matrix((0,len(grid_ids)*3));wall_bound=np.zeros(0)
            if boundary is not None and 'pipe_end' in boundary:
                from lava_mpm_inlet import conduit_constraints
                wallC,wall_bound=conduit_constraints(self.x,self.v,local,w,len(grid_ids),dx,dt,boundary)
            pipe_rows=wallC.shape[0]
            if self.ground:
                from lava_mpm_inlet import solid_ground_constraints
                radius=.5*self.sample_size[2]*np.cbrt(self.volume/np.prod(self.sample_size))
                floorC,floor_bound=solid_ground_constraints(self.x,self.volume,self.connectivity.frozen,self.v,local,w,len(grid_ids),hz,dt,self.gravity,radius)
                wallC=vstack([wallC,floorC],format='csr');wall_bound=np.r_[wall_bound,floor_bound]
            has_contact=bool(split_nodes or wallC.shape[0])
            if has_contact:
                fragmentC,pairs=contact_matrix(grid_ids,local,grad,self.mass,ma,np.cbrt(cell_volume),m.density) if split_nodes else (csr_matrix((0,len(grid_ids)*3)),np.zeros((0,2)))
                contactC=vstack([fragmentC,wallC],format='csr')
                offset=contactC@lift-np.r_[np.zeros(fragmentC.shape[0]),wall_bound]
                contact_solve=implicit_contact
                if self.contact_solver=='admm':
                    from lava_mpm_contact_admm import contact as contact_solve
                u,mechanical_residual,multipliers,contact_objective_loss,contact_iterations=contact_solve(A,rhs,S,contactC,1/(m.young*np.cbrt(cell_volume)*dt*dt),offset)
                contact_count=int((multipliers>0).sum())
                impulse=np.asarray(fragmentC.T@multipliers[:fragmentC.shape[0]]).reshape(-1,3);contact_error=float(np.linalg.norm(impulse.sum(0)))
                wall_impulse=np.asarray(wallC[:pipe_rows].T@multipliers[fragmentC.shape[0]:fragmentC.shape[0]+pipe_rows]).reshape(-1,3).sum(0)
                self.ledger['conduit_impulse_norm']=self.ledger.get('conduit_impulse_norm',0.)+float(np.linalg.norm(wall_impulse))
                floor_impulse=np.asarray(wallC[pipe_rows:].T@multipliers[fragmentC.shape[0]+pipe_rows:]).reshape(-1,3).sum(0)
                self.ledger['solid_floor_impulse_norm']=self.ledger.get('solid_floor_impulse_norm',0.)+float(np.linalg.norm(floor_impulse))
                self.ledger['contact_objective_loss']=self.ledger.get('contact_objective_loss',0.)+contact_objective_loss
            else:
                reducedu=spsolve(reducedA.tocsc(),reducedrhs);u=S@reducedu
                mechanical_residual=float(np.linalg.norm(reducedA@reducedu-reducedrhs)/max(np.linalg.norm(reducedrhs),1e-30))
            u=u+lift
            if mechanical_residual>1e-5 or not np.isfinite(u).all():raise RuntimeError(('Implicit mechanics failed',mechanical_residual))
            un=u.reshape(-1,3)
            if boundary is not None or node_velocity is not None:
                reaction=A@u-original_rhs
                if has_contact:reaction+=contactC.T@multipliers
                work=float(lift@reaction)
                work_key='inlet_boundary_work' if boundary is not None else 'prescribed_boundary_work'
                self.ledger[work_key]=self.ledger.get(work_key,0.)+work
            if self.ground:
                contact=np.flatnonzero((abs(xyz[:,2])<hz*1e-7)&grounded);reaction=(A@u-rhs).reshape(-1,3)[contact,2]
                speed=np.linalg.norm(un[contact,:2],axis=1)
                factor=np.maximum(0,1-m.friction*np.maximum(reaction,0)/(safe[contact]*np.maximum(speed,1e-30)))
                un[contact,:2]*=factor[:,None]
            rate=np.asarray(Bdev@un.ravel()).reshape(n,6)
            elasticdev=olddev+2*(network_viscosity*surviving)[:,None]*rate
            newdev=elasticdev+2*solvent_viscosity[:,None]*rate
            dilation_rate=np.asarray(P@un.ravel()).ravel()[ci]
            newdilation=strain0+dt*dilation_rate
            newdilation=np.where(can_tension,newdilation,np.minimum(newdilation,0))
            fullstress=tensor(newdev)+np.eye(3)[None]*(bulk*newdilation)[:,None,None]
            eig,vectors=np.linalg.eigh(fullstress);self.principal_direction=vectors[:,:,-1];eig=eig[:,-1]/surviving
            fracture_length=1/np.sqrt(np.sum((self.principal_direction/cell_size)**2,axis=1))
            history,damage=tensile_damage(self.history,self.damage,eig,m.young,m.tensile_strength,m.fracture_energy,fracture_length)
            # Liquid has no fracture history. Melting releases an existing
            # network; a future cooled network starts stress free.
            damage=np.where(solid>self.failure_fraction,damage,0);history=np.where(solid>self.failure_fraction,history,0)
            delta=np.maximum(0,damage-self.damage)
            elastic_energy=self.volume*(np.sum(elasticdev*elasticdev,axis=1)/(4*np.maximum(shear,1))+bulk*newdilation**2/2)
            fracture_work=delta*elastic_energy
            fracture_j=float(np.sum(fracture_work));self.ledger['fracture']+=fracture_j
            damage_ratio=(1-damage)/np.maximum(1-constitutive_damage,1e-12)
            elasticdev*=damage_ratio[:,None]
            # Maxwell dissipation is converted into enthalpy, not discarded.
            dissipation=dt*self.volume*(np.sum(elasticdev*elasticdev,axis=1)*network_fluidity/2+2*solvent_viscosity*np.sum(rate*rate,axis=1))
            if len(interface_pairs):
                ia,ib=interface_pairs.T
                pair_heat=interface_coeff*np.sum((un[ia]-un[ib])**2,axis=1)
                grid_heat=np.bincount(np.r_[ia,ib],weights=np.tile(pair_heat*.5,2),minlength=len(ma))
                particle_heat=self.mass*np.sum(w*(grid_heat/safe)[local],axis=1)
                dissipation+=particle_heat
                self.ledger['interface_heat']=self.ledger.get('interface_heat',0.)+float(particle_heat.sum())
            viscous_j=float(dissipation.sum());self.h+=dissipation/self.mass;self.ledger['viscous_heat']+=viscous_j
            newv=np.sum(w[:,:,None]*un[local],axis=1)
            newC=4*np.einsum('pk,pki,pkj->pij',w,un[local],dp)/cell_size[None,None,:]**2
            velocity_gradient=np.einsum('pki,pkj->pij',un[local],grad)
            update=np.eye(3)[None]+dt*velocity_gradient
            # Rotate the deviatoric stress with the local polar rotation.
            U,_,Vh=np.linalg.svd(update);rotation=U@Vh
            newdev=mandel(rotation@tensor(elasticdev)@rotation.transpose(0,2,1))
            self.F=update@self.F
            # Use the same B-bar volume rate used in the pressure equation.
            # Positive dilation in a cavitating liquid opens empty space;
            # it must not increase the amount of liquid material.
            self.volume=self.mass/m.density*np.exp(newdilation+self.thermal_volume)
            if self.ground:
                # Unilateral material-point contact catches subcell impacts
                # missed by the grid boundary. The impulse is applied to
                # velocity before advection, with a Coulomb friction cone.
                hit=self.x[:,2]+dt*newv[:,2]<0
                before=newv[hit].copy();normal_delta=-self.x[hit,2]/dt-newv[hit,2]
                newv[hit,2]+=normal_delta
                tangent=np.linalg.norm(newv[hit,:2],axis=1)
                newv[hit,:2]*=np.maximum(0,1-m.friction*normal_delta/np.maximum(tangent,1e-30))[:,None]
                self.ledger['ground_impulse']=self.ledger.get('ground_impulse',0.)+float(np.sum(self.mass[hit]*normal_delta))
                self.ledger['ground_dissipation']=self.ledger.get('ground_dissipation',0.)+float(np.sum(self.mass[hit]*(np.sum(before**2,axis=1)-np.sum(newv[hit]**2,axis=1))*.5))
                newC[hit,2,:]=0
            self.x+=dt*newv;self.v=newv;self.C=newC
            self.deviator=newdev;self.dilation=newdilation;self.damage=damage;self.history=history
            if gas is not None and fracture_j>0:
                # A declared 1% of fracture work creates unresolved basalt
                # surface area. Its mass and enthalpy leave the material and
                # enter the gas aerosol fields at the fracture location.
                specific_surface_energy=3*m.fracture_energy/(2*m.density*gas.dust_radius)
                dust_mass=np.minimum(.01*fracture_work/specific_surface_energy,self.mass*.001)
                take=dust_mass>0
                if take.any():
                    gas.add_fracture_dust(self.x[take],dust_mass[take],self.h[take],m)
                    self.ledger['dust_mass_out']=self.ledger.get('dust_mass_out',0.)+float(dust_mass.sum())
                    self.ledger['dust_enthalpy_out']=self.ledger.get('dust_enthalpy_out',0.)+float(dust_mass@self.h)
                    self.volume*=1-dust_mass/self.mass;self.mass-=dust_mass
            if self.ground and self.x[:,2].min() < -hz*.2:raise RuntimeError('Ground penetration exceeded 0.2 grid cells')
            self.last_grid=dict(xyz=xyz,velocity=un,mass=ma)
        self.time+=dt
        total=float(self.mass@self.h)
        balance=total-self.initial_energy-self.ledger.get('source_enthalpy',0.)+self.ledger['radiation']+self.ledger['convection']+self.ledger['bed']-self.ledger['viscous_heat']-self.ledger.get('contact_heat',0.)+self.ledger.get('dust_enthalpy_out',0.)
        mass_error=float(self.mass.sum()-self.initial_mass-self.ledger.get('source_mass',0.)+self.ledger.get('dust_mass_out',0.))
        row=dict(time=self.time,dt=dt,particles=n,mass=float(self.mass.sum()),volume=float(self.volume.sum()),
                 temperatureRange=[float(temperature.min()),float(temperature.max())],meanSolidFraction=float(solid.mean()),
                 solidParticles=int((solid>.8).sum()),damagedParticles=int((self.damage>.1).sum()),maximumDamage=float(self.damage.max()),
                 maximumSpeed=float(np.linalg.norm(self.v,axis=1).max()),thermalBalanceRelative=abs(balance)/max(abs(self.initial_energy),1),
                 stepHeatResidualJ=thermal_error,mechanicalResidual=mechanical_residual,heatNewtonIterations=heat_iters,
                 viscousHeatJ=viscous_j,fractureEnergyJ=fracture_j,seconds=time.time()-start)
        row.update(materialVelocityFields=int(len(np.unique(self.connectivity.labels))),brokenConnectivityEdges=int(self.connectivity.broken.sum()),contactImpulses=contact_count,contactMomentumError=contact_error)
        row['splitGridNodes']=split_nodes
        row['massBalanceErrorKg']=mass_error
        if abs(mass_error)>max(self.initial_mass,1)*1e-10:raise RuntimeError('Source mass ledger failed')
        if not np.isfinite(self.x).all() or not np.isfinite(self.h).all():raise RuntimeError('Nonfinite simulation state')
        if row['thermalBalanceRelative']>1e-6:raise RuntimeError(('Thermal energy balance failed',row))
        self.rows.append(row)
        return row

    def save(self,folder):
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
        state={k:getattr(self,k) for k in ('x','rest','v','C','F','mass','volume','h','deviator','dilation','damage','history','thermal_volume','principal_direction')}
        state.update(bond_edges=self.connectivity.edges,bond_broken=self.connectivity.broken,bond_frozen=self.connectivity.frozen,labels=self.connectivity.labels)
        state.update(temperature=self.material.temperature(self.h),solid=self.material.solid(self.material.temperature(self.h)),time=self.time)
        path=folder/'state.npz';temp=folder/'state.partial.npz';np.savez_compressed(temp,**state);temp.replace(path)
        meta=dict(material=asdict(self.material),dx=self.dx,spacing=self.spacing,cell_size=self.cell_size.tolist(),sample_size=self.sample_size.tolist(),contact_solver=self.contact_solver,bonded_bed=self.bonded_bed,coherent_fraction=self.coherent_fraction,failure_fraction=self.failure_fraction,origin=self.origin.tolist(),shape=self.shape,gravity=self.gravity.tolist(),ground=self.ground,
                  initial_energy=self.initial_energy,initial_mass=self.initial_mass,ledger=self.ledger,time=self.time,rows=self.rows)
        tmp=folder/'state.partial.json';tmp.write_text(json.dumps(meta,indent=2));tmp.replace(folder/'state.json')

    @classmethod
    def load(cls,folder):
        folder=Path(folder);meta=json.loads((folder/'state.json').read_text());s=np.load(folder/'state.npz')
        obj=cls(s['x'],meta['spacing'],meta['dx'],material=Material(**meta['material']),origin=meta['origin'],shape=meta['shape'],gravity=meta['gravity'],ground=meta['ground'],cell_size=meta.get('cell_size'),sample_size=meta.get('sample_size'),contact_solver=meta.get('contact_solver','dense'),bonded_bed=meta.get('bonded_bed',False),coherent_fraction=meta.get('coherent_fraction',.85),failure_fraction=meta.get('failure_fraction',.8))
        for k in ('x','rest','v','C','F','mass','volume','h','deviator','dilation','damage','history','thermal_volume','principal_direction'):
            if k in s:setattr(obj,k,s[k].copy())
        if 'bond_edges' in s:
            obj.connectivity.edges=s['bond_edges'].copy();obj.connectivity.broken=s['bond_broken'].copy();obj.connectivity.frozen=s['bond_frozen'].copy();obj.connectivity.labels=s['labels'].copy()
        for k in ('initial_energy','initial_mass','ledger','time','rows'):setattr(obj,k,meta[k])
        return obj


def block(lo,hi,spacing):
    step=np.broadcast_to(np.asarray(spacing),(3,))
    return np.array(np.meshgrid(*[np.arange(lo[i]+step[i]/2,hi[i],step[i]) for i in range(3)],indexing='ij')).reshape(3,-1).T
