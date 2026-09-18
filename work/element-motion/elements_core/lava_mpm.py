"""Three-dimensional thermal viscoelastic material-point lava on the CPU.

This is a reduced-compressibility research/graphics model, not a calibrated
volcanology solver. Particles carry mass, velocity, affine velocity, volume,
specific enthalpy, a corotational Maxwell deviatoric stress and plastic damage.
The quadratic APIC/MLS transfer is a single continuum: there are NO rigid pieces,
keyframed per-piece transforms, or animated procedural displacement.

The enthalpy-to-temperature map has a finite mushy interval. Conservative nodal
heat exchange is transferred as an enthalpy increment, not a PIC temperature
reset. Surface convection/radiation remove measured energy. A Maxwell stress
relaxes to a viscous response in the melt and retains shear in the cooled crust;
a radial J2 return map limits stress. This is not a fracture-surface solver.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import math
import numpy as np
from numba import njit, prange
from scipy.ndimage import map_coordinates


@dataclass(frozen=True)
class LavaConfig:
    spacing: float = .016
    shape: tuple[int, int, int] = (145, 97, 65)
    origin: tuple[float, float, float] = (-1.152, -.768, 0.)
    density: float = 2600.
    bulk_modulus: float = 180000.
    shear_modulus: float = 60000.
    melt_viscosity: float = 80.
    crust_yield: float = 6500.
    heat_capacity: float = 1200.
    latent_heat: float = 400000.
    solidus: float = 1250.
    liquidus: float = 1450.
    ambient: float = 293.15
    conductivity: float = 2.0
    convection: float = 12.
    emissivity: float = .9
    gravity: float = 9.81
    floor: float = .032
    friction: float = .46
    max_dt: float = .00055
    cfl: float = .25
    support_start: float = .22
    support_end: float = .62

    def __post_init__(self):
        if min(self.shape) < 8 or self.spacing<=0 or self.density<=0:
            raise ValueError('Invalid grid or density')
        if self.liquidus<=self.solidus or self.solidus<=self.ambient:
            raise ValueError('Invalid phase temperatures')
        if not 0 < self.cfl <= .5 or self.max_dt<=0 or self.melt_viscosity<=0:
            raise ValueError('Invalid stability/viscosity settings')
        if min(self.bulk_modulus,self.shear_modulus,self.heat_capacity,self.latent_heat)<=0 or min(self.conductivity,self.convection,self.emissivity,self.friction)<0:
            raise ValueError('Invalid constitutive coefficients')
        if self.support_end<=self.support_start:
            raise ValueError('Invalid support interval')

    def array(self):
        return np.array([self.spacing, self.density, self.bulk_modulus,
            self.shear_modulus,self.melt_viscosity,self.crust_yield,
            self.heat_capacity,self.latent_heat,self.solidus,self.liquidus,
            self.ambient,self.conductivity,self.convection,self.emissivity,
            self.gravity,self.floor,self.friction],dtype=np.float64)


def enthalpy_from_temperature(T, cfg: LavaConfig):
    T=np.asarray(T,dtype=np.float64)
    return cfg.heat_capacity*(T-cfg.ambient)+cfg.latent_heat*np.clip((T-cfg.solidus)/(cfg.liquidus-cfg.solidus),0,1)


def temperature_from_enthalpy(H, cfg: LavaConfig):
    H=np.asarray(H,dtype=np.float64)
    h0=cfg.heat_capacity*(cfg.solidus-cfg.ambient)
    h1=cfg.heat_capacity*(cfg.liquidus-cfg.ambient)+cfg.latent_heat
    return np.where(H<h0,cfg.ambient+H/cfg.heat_capacity,np.where(H>h1,
        cfg.ambient+(H-cfg.latent_heat)/cfg.heat_capacity,
        cfg.solidus+(H-h0)/(cfg.heat_capacity+cfg.latent_heat/(cfg.liquidus-cfg.solidus))))


@njit(cache=True, inline='always')
def _T(H,p):
    cp,L,Ts,Tl,amb=p[6],p[7],p[8],p[9],p[10]
    h0=cp*(Ts-amb); h1=cp*(Tl-amb)+L
    if H<h0:return amb+H/cp
    if H>h1:return amb+(H-L)/cp
    return Ts+(H-h0)/(cp+L/(Tl-Ts))


@njit(cache=True, inline='always')
def _weights(f):
    w=np.empty(3,np.float64)
    w[0]=.5*(1.5-f)**2;w[1]=.75-(f-1.)**2;w[2]=.5*(f-.5)**2
    return w


@njit(cache=True, inline='always')
def _det(a):
    return a[0,0]*(a[1,1]*a[2,2]-a[1,2]*a[2,1])-a[0,1]*(a[1,0]*a[2,2]-a[1,2]*a[2,0])+a[0,2]*(a[1,0]*a[2,1]-a[1,1]*a[2,0])


@njit(cache=True, inline='always')
def _mul3(a,b):
    c=np.zeros((3,3),np.float64)
    for i in range(3):
        for j in range(3):
            for k in range(3):c[i,j]+=a[i,k]*b[k,j]
    return c


@njit(cache=True)
def particle_to_grid(x,v,C,J,H,S,damage,mass,volume0,origin,params,dt,gm,gv,gH,viscous_heat):
    """Quadratic APIC transfer with MLS stress divergence. Serial scatter is
    deliberate: no races/atomic-order dependence in the authoritative CPU path.
    """
    gm.fill(0.);gv.fill(0.);gH.fill(0.)
    dx=params[0]; inv=1/dx; rho=params[1]; K=params[2]
    for q in range(len(x)):
        T=_T(H[q],params)
        solid=min(1.,max(0.,(params[9]-T)/(params[9]-params[8])))
        G=params[3]*(.10+.90*solid)
        eta=params[4]*math.exp(10.*solid)*(1.-.90*damage[q])
        D=.5*(C[q]+C[q].T)
        tr=(D[0,0]+D[1,1]+D[2,2])/3
        for a in range(3):D[a,a]-=tr
        W=.5*(C[q]-C[q].T)
        A=.5*dt*W
        den=1.+A[2,1]**2+A[0,2]**2+A[1,0]**2
        R=np.eye(3)+2./den*(A+_mul3(A,A))
        rotated=_mul3(_mul3(R,S[q]),R.T)
        decay=math.exp(-dt*G/eta)
        stress=decay*rotated+2.*eta*(1.-decay)*D
        trace=(stress[0,0]+stress[1,1]+stress[2,2])/3
        for a in range(3):stress[a,a]-=trace
        seq=math.sqrt(1.5*np.sum(stress*stress))
        Y=params[5]*(.03+solid*solid)*(1.-.8*damage[q])
        plastic_heat=0.
        if solid>.25 and seq>Y:
            eps=(seq-Y)/(3*G)
            damage[q]=min(.98,damage[q]+eps*2.5*solid)
            returned=stress*(Y/seq)
            plastic_heat=max(0.,(np.sum(stress*stress)-np.sum(returned*returned))/(4*G*rho))
            stress=returned
        S[q]=stress
        diss=dt*np.sum(stress*stress)/(2*eta*rho)+plastic_heat
        H[q]+=diss
        viscous_heat[0]+=diss*mass[q]
        sigma=stress.copy()
        pressure=K/4.*(J[q]**-4-1.)
        for a in range(3):sigma[a,a]-=pressure
        affine=mass[q]*C[q]-dt*volume0[q]*J[q]*4*inv*inv*sigma
        gpos=(x[q]-origin)*inv
        base=np.floor(gpos-.5).astype(np.int64);f=gpos-base
        wx,wy,wz=_weights(f[0]),_weights(f[1]),_weights(f[2])
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    weight=wx[i]*wy[j]*wz[k]
                    ii,jj,kk=base[0]+i,base[1]+j,base[2]+k
                    rel=np.array([(i-f[0])*dx,(j-f[1])*dx,(k-f[2])*dx])
                    mom=np.zeros(3)
                    for a in range(3):
                        mom[a]=mass[q]*v[q,a]
                        for b in range(3):mom[a]+=affine[a,b]*rel[b]
                    gm[ii,jj,kk]+=weight*mass[q]
                    gH[ii,jj,kk]+=weight*mass[q]*H[q]
                    for a in range(3):gv[ii,jj,kk,a]+=weight*mom[a]


@njit(cache=True)
def grid_velocity_and_heat(gm,gv,gH,gT,dE,origin,p,dt,support,loss):
    nx,ny,nz=gm.shape;dx=p[0];rho=p[1]
    dE.fill(0.);gT.fill(p[10]);loss.fill(0.)
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                m=gm[i,j,k]
                if m<1e-14:continue
                for a in range(3):gv[i,j,k,a]/=m
                gv[i,j,k,2]-=dt*p[14]*(1-support)
                z=origin[2]+k*dx
                if z<=p[15]+dx and gv[i,j,k,2]<0:
                    normal=-gv[i,j,k,2];gv[i,j,k,2]=0.
                    tangent=math.sqrt(gv[i,j,k,0]**2+gv[i,j,k,1]**2)
                    factor=max(0.,1-p[16]*normal/max(tangent,1e-20))
                    gv[i,j,k,0]*=factor;gv[i,j,k,1]*=factor
                if i<3 and gv[i,j,k,0]<0:gv[i,j,k,0]=0.
                if i>nx-4 and gv[i,j,k,0]>0:gv[i,j,k,0]=0.
                if j<3 and gv[i,j,k,1]<0:gv[i,j,k,1]=0.
                if j>ny-4 and gv[i,j,k,1]>0:gv[i,j,k,1]=0.
                if k>nz-4 and gv[i,j,k,2]>0:gv[i,j,k,2]=0.
                gH[i,j,k]/=m;gT[i,j,k]=_T(gH[i,j,k],p)
    for i in range(1,nx-1):
        for j in range(1,ny-1):
            for k in range(1,nz-1):
                m=gm[i,j,k]
                if m<1e-14:continue
                occ=min(1.,m/(rho*dx**3));T=gT[i,j,k]
                for axis in range(3):
                    ii,jj,kk=i+(axis==0),j+(axis==1),k+(axis==2)
                    other=gm[ii,jj,kk]
                    if other>1e-14:
                        occ2=min(1.,other/(rho*dx**3))
                        conductance=p[11]*dx*2*occ*occ2/(occ+occ2)
                        Q=dt*conductance*(gT[ii,jj,kk]-T)
                        if dt*conductance/min(m,other)/p[6]>.4:
                            raise ValueError('Thermal diffusion CFL exceeded')
                        dE[i,j,k]+=Q;dE[ii,jj,kk]-=Q
                area=0.
                for di,dj,dk in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
                    occ2=min(1.,gm[i+di,j+dj,k+dk]/(rho*dx**3))
                    area+=max(0.,occ-occ2)*dx*dx
                radiative=p[13]*5.670374419e-8*area*(T**4-p[10]**4)*dt
                convective=p[12]*area*(T-p[10])*dt
                if radiative+convective>m*gH[i,j,k]*.2:
                    raise ValueError('Surface heat timestep too large')
                dE[i,j,k]-=radiative+convective
                loss[0]+=radiative;loss[1]+=convective
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                if gm[i,j,k]>1e-14:dE[i,j,k]/=gm[i,j,k]


@njit(cache=True)
def grid_to_particle(x,v,C,J,H,origin,p,dt,gv,dE,contact_count):
    dx=p[0];inv=1/dx
    for q in range(len(x)):
        gp=(x[q]-origin)*inv
        base=np.floor(gp-.5).astype(np.int64);f=gp-base
        wx,wy,wz=_weights(f[0]),_weights(f[1]),_weights(f[2])
        newv=np.zeros(3);newC=np.zeros((3,3));deltaH=0.
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    weight=wx[i]*wy[j]*wz[k]
                    vel=gv[base[0]+i,base[1]+j,base[2]+k]
                    deltaH+=weight*dE[base[0]+i,base[1]+j,base[2]+k]
                    rel=np.array([(i-f[0])*dx,(j-f[1])*dx,(k-f[2])*dx])
                    newv+=weight*vel
                    for a in range(3):
                        for b in range(3):newC[a,b]+=4*inv*inv*weight*vel[a]*rel[b]
        J[q]*=_det(np.eye(3)+dt*newC)
        C[q]=newC;v[q]=newv;x[q]+=dt*newv;H[q]+=deltaH
        if x[q,2]<p[15]+.0001:
            x[q,2]=p[15]+.0001;v[q,2]=max(0.,v[q,2]);contact_count[0]+=1


def sample_glyph(source: Path, config: LavaConfig, *, samples_per_axis=2, scale=.15, offset=.18):
    """Sample the original signed distance glyph into a genuine 3D extrusion.
    Shape is inherited from the repository; no substituted font or new logo.
    """
    if samples_per_axis<1 or scale<=0:raise ValueError('Invalid source sampling')
    with np.load(source,allow_pickle=False) as data:
        sdf=data['sdf'];lo=data['lo'];extent=data['extent']
    step=config.spacing/samples_per_axis
    x=np.arange(-.7,.7,step)+step*.5
    y=np.arange(-.08,.08,step)+step*.5
    z=np.arange(.15,.78,step)+step*.5
    xx,yy,zz=np.meshgrid(x,y,z,indexing='ij')
    p=np.column_stack([xx.ravel(),yy.ravel(),zz.ravel()])
    origx=p[:,0]/scale;origz=(p[:,2]-offset)/scale
    coords=np.array([(origz-lo[2])/extent[2]*sdf.shape[0]-.5,
                     (origx-lo[0])/extent[0]*sdf.shape[1]-.5])
    d=map_coordinates(sdf,coords,order=1,mode='constant',cval=-1.)*scale
    depth=.035+.026*np.sqrt(np.clip(d/.038,0,1))
    keep=(d>0)&(np.abs(p[:,1])<depth)
    p=p[keep];d=d[keep];depth=depth[keep]
    boundary=np.minimum(d,depth-np.abs(p[:,1]))
    cool=.5+.5*np.sin(p[:,0]*83+p[:,2]*47)*np.cos(p[:,0]*39-p[:,2]*67)
    skin_depth=config.spacing*(.62+.85*cool)
    blend=np.clip(boundary/skin_depth,0,1)
    T=1020+490*blend
    rng=np.random.default_rng(7319)
    jitter=(rng.random(p.shape)-.5)*step*.18
    p+=jitter
    return p,enthalpy_from_temperature(T,config),np.full(len(p),step**3)


class LavaMPM:
    def __init__(self,config:LavaConfig,positions,enthalpy,particle_volumes):
        self.config=config;self.params=config.array();self.origin=np.array(config.origin)
        self.x=np.array(positions,dtype=np.float64,copy=True);self.rest=self.x.copy()
        n=len(self.x)
        if self.x.shape!=(n,3) or n==0:raise ValueError('Invalid particle positions')
        self.v=np.zeros((n,3));self.C=np.zeros((n,3,3));self.J=np.ones(n)
        self.H=np.array(enthalpy,dtype=np.float64,copy=True)
        self.V0=np.array(particle_volumes,dtype=np.float64,copy=True)
        if self.H.shape!=(n,) or self.V0.shape!=(n,) or np.any(self.V0<=0):raise ValueError('Invalid particle state')
        self.mass=self.V0*config.density
        self.S=np.zeros((n,3,3));self.damage=np.zeros(n)
        self.gm=np.zeros(config.shape);self.gv=np.zeros((*config.shape,3))
        self.gH=np.zeros(config.shape);self.gT=np.zeros(config.shape);self.dE=np.zeros(config.shape)
        self.time=0.;self.steps=0;self.radiative_loss=0.;self.convective_loss=0.;self.viscous_heat=0.
        self.initial_energy=float(self.mass@self.H);self.contact_corrections=0
        self.initial_count=n
        self.injected_particles=0;self.injected_mass=0.;self.injected_energy=0.
        self._loss=np.zeros(2);self._visc=np.zeros(1);self._contact=np.zeros(1,np.int64)
        self.validate()

    def inject(self,positions,enthalpy,particle_volumes,velocities=None,material_coordinates=None):
        """Inject an open-boundary source batch without kinematic target forces.

        Source particles enter at their physical inlet state.  Their mass and
        enthalpy are added to the run's conservation reference at injection
        time, so subsequent balance metrics remain meaningful.
        """
        x=np.asarray(positions,dtype=np.float64)
        n=len(x)
        if n==0:return 0
        H=np.asarray(enthalpy,dtype=np.float64)
        V=np.asarray(particle_volumes,dtype=np.float64)
        if x.shape!=(n,3) or H.shape!=(n,) or V.shape!=(n,) or np.any(V<=0):
            raise ValueError('Invalid injected particle state')
        if velocities is None:v=np.zeros((n,3),np.float64)
        else:
            v=np.asarray(velocities,dtype=np.float64)
            if v.shape!=(n,3):raise ValueError('Invalid injected velocity state')
        rest=x.copy() if material_coordinates is None else np.asarray(material_coordinates,dtype=np.float64)
        if rest.shape!=(n,3):raise ValueError('Invalid injected material coordinates')
        if not all(np.isfinite(a).all() for a in (x,H,V,v,rest)):
            raise FloatingPointError('Nonfinite injected source state')
        mass=V*self.config.density
        self.x=np.concatenate((self.x,x),axis=0)
        self.rest=np.concatenate((self.rest,rest),axis=0)
        self.v=np.concatenate((self.v,v),axis=0)
        self.C=np.concatenate((self.C,np.zeros((n,3,3),np.float64)),axis=0)
        self.J=np.concatenate((self.J,np.ones(n,np.float64)),axis=0)
        self.H=np.concatenate((self.H,H),axis=0)
        self.V0=np.concatenate((self.V0,V),axis=0)
        self.mass=np.concatenate((self.mass,mass),axis=0)
        self.S=np.concatenate((self.S,np.zeros((n,3,3),np.float64)),axis=0)
        self.damage=np.concatenate((self.damage,np.zeros(n,np.float64)),axis=0)
        added_energy=float(mass@H)
        self.initial_energy+=added_energy
        self.initial_count+=n
        self.injected_particles+=n
        self.injected_mass+=float(mass.sum())
        self.injected_energy+=added_energy
        self.validate()
        return n

    def support(self,t):
        c=self.config
        a=np.clip((t-c.support_start)/(c.support_end-c.support_start),0.,1.)
        return 1-a*a*(3-2*a)

    def validate(self):
        c=self.config
        if not all(np.isfinite(a).all() for a in [self.x,self.v,self.C,self.J,self.H,self.S,self.damage]):
            raise FloatingPointError('Nonfinite material point state')
        if np.any(self.J<=.35) or np.any(self.J>=2.):
            raise FloatingPointError(f'Material volume out of validity range: {self.J.min()}, {self.J.max()}')
        cells=(self.x-self.origin)/c.spacing
        if np.any(cells[:,:2]<6.) or np.any(cells[:,:2]>np.array(c.shape[:2])-6.) or np.any(cells[:,2]>c.shape[2]-6.):
            raise FloatingPointError('Non-floor boundary is too close: enlarge the simulation domain')
        if np.any(cells<1.5) or np.any(cells>np.array(c.shape)-2.5):
            raise FloatingPointError('Particle left the supported transfer domain')
        if np.any(self.H<0):raise FloatingPointError('Negative enthalpy')
        if len(self.x)!=self.initial_count:raise AssertionError('Material particle count changed')

    def step(self,dt):
        if not 0<dt<=self.config.max_dt*(1+1e-9):raise ValueError('Invalid timestep')
        self._visc.fill(0);self._contact.fill(0)
        particle_to_grid(self.x,self.v,self.C,self.J,self.H,self.S,self.damage,self.mass,self.V0,
            self.origin,self.params,dt,self.gm,self.gv,self.gH,self._visc)
        grid_velocity_and_heat(self.gm,self.gv,self.gH,self.gT,self.dE,self.origin,self.params,dt,
            self.support(self.time+dt*.5),self._loss)
        grid_to_particle(self.x,self.v,self.C,self.J,self.H,self.origin,self.params,dt,self.gv,self.dE,self._contact)
        self.radiative_loss+=self._loss[0];self.convective_loss+=self._loss[1]
        self.viscous_heat+=self._visc[0];self.contact_corrections+=int(self._contact[0])
        self.time+=dt;self.steps+=1
        if self.steps%12==0:self.validate()

    def advance(self,duration):
        if duration<0 or not math.isfinite(duration):raise ValueError('Invalid duration')
        target=self.time+duration;c=self.config
        speed=float(np.linalg.norm(self.v,axis=1).max())
        wave=math.sqrt((c.bulk_modulus+4*c.shear_modulus/3)/c.density)
        while target-self.time>1e-12:
            if self.steps%12==0:
                speed=float(np.linalg.norm(self.v,axis=1).max())
                compression=max(1.,float(self.J.min())**-1.5)
                wave=math.sqrt((c.bulk_modulus+4*c.shear_modulus/3)/c.density)*compression
            dt=min(target-self.time,c.max_dt,c.cfl*c.spacing/(wave+speed))
            self.step(dt)
        self.validate()
        return self.metrics()

    def metrics(self):
        c=self.config;T=temperature_from_enthalpy(self.H,c)
        expected=self.initial_energy+self.viscous_heat-self.radiative_loss-self.convective_loss
        thermal_energy=float(self.mass@self.H)
        return {'time':self.time,'steps':self.steps,'particles':len(self.x),'massKg':float(self.mass.sum()),
            'sourceInjectedParticles':int(self.injected_particles),'sourceInjectedMassKg':float(self.injected_mass),
            'sourceInjectedEnergyJ':float(self.injected_energy),
            'massDifferenceKg':float(self.mass.sum()-self.V0.sum()*c.density),
            'initialVolumeM3':float(self.V0.sum()),'currentVolumeM3':float(self.V0@self.J),
            'volumeChangeRelative':float((self.V0@self.J)/self.V0.sum()-1),
            'volumeRatioMin':float(self.J.min()),'volumeRatioMax':float(self.J.max()),
            'temperatureMinK':float(T.min()),'temperatureMaxK':float(T.max()),
            'solidFractionMean':float(np.clip((c.liquidus-T)/(c.liquidus-c.solidus),0,1).mean()),
            'thermalEnergyJ':thermal_energy,'radiationLossJ':self.radiative_loss,
            'convectionLossJ':self.convective_loss,'viscoplasticHeatJ':self.viscous_heat,
            'thermalBalanceRelative':float((thermal_energy-expected)/max(self.initial_energy,1e-12)),
            'maxSpeed':float(np.linalg.norm(self.v,axis=1).max()),'maxDamage':float(self.damage.max()),
            'deviatoricStressRMSPa':float(np.sqrt(np.mean(self.S**2))),
            'particleFloorCorrections':self.contact_corrections,'minHeight':float(self.x[:,2].min()),
            'boundsMin':self.x.min(0).tolist(),'boundsMax':self.x.max(0).tolist(),
            'nonFloorBoundaryGuardPassed':True}

    def snapshot(self):
        return dict(positions=self.x,velocities=self.v,affine=self.C,volumeRatio=self.J,
            enthalpy=self.H,temperature=temperature_from_enthalpy(self.H,self.config),
            particleVolume=self.V0,stress=self.S,damage=self.damage,rest=self.rest,time=np.float64(self.time))
