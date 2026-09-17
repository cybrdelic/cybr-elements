"""CPU low-Mach, variable-density MAC gas with conservative mass transport.

Constant-pressure ideal-gas enthalpy makes div(alpha*u) = Q/H-d(alpha)/dt.
The MPM volume fraction supplies alpha, so material motion displaces gas.
This is a diffuse-interface, dilute-water model, not resolved bubble chemistry.
No noise, vorticity confinement, smoke opacity source, or scripted velocity.
"""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import numpy as np
import json
from scipy.sparse import coo_matrix,diags
from scipy.sparse.linalg import cg,splu
from scipy.ndimage import map_coordinates,gaussian_filter
from scipy.spatial import cKDTree
from lava_mpm import Material


class Gas:
    def __init__(self,origin=(-.10,-.08,0.),shape=(24,16,26),dx=.01):
        self.origin=np.array(origin);self.shape=tuple(shape);self.dx=dx
        self.cp=1005.;self.R=287.05;self.ambient=293.15;self.pressure0=101325.;self.rho0=self.pressure0/(self.R*self.ambient)
        self.H=self.pressure0*self.cp/self.R;self.air_viscosity=1.81e-5;self.conductivity=.026;self.latent=2.26e6
        self.xyz=self.origin+(np.moveaxis(np.indices(shape),0,-1)+.5)*dx
        self.alpha=np.ones(shape);self.mass=np.full(shape,self.rho0*dx**3)
        self.vapor=np.full(shape,self.rho0*.008*dx**3);self.liquid=np.zeros(shape)
        self.dust=np.zeros(shape);self.dust_h=np.zeros(shape);self.dust_radius=3e-6;self.dust_material=Material()
        self.vel=[np.zeros(tuple(n+(i==a) for i,n in enumerate(shape))) for a in range(3)]
        self.face_coords=[np.indices(v.shape).astype(float)+np.array([0 if i==a else .5 for i in range(3)])[:,None,None,None] for a,v in enumerate(self.vel)]
        self.p=np.zeros(shape);self.pending_heat=np.zeros(shape);self.pending_vapor=np.zeros(shape)
        self.ledger=dict(heat_in=0.,mass_out=0.,water_in=0.,water_out=0.,heat_out=0.,pressure_work_error=0.,dust_in=0.,dust_out=0.,dust_enthalpy_in=0.,dust_enthalpy_out=0.,dust_heat_to_air=0.,conduction_out=0.)
        self.initial_mass=float(self.mass.sum());self.initial_water=float(self.vapor.sum());self.time=0.;self.rows=[]

    @property
    def temperature(self):
        return self.H*self.alpha*self.dx**3/(self.cp*np.maximum(self.mass,1e-30))

    def sample(self,field,xyz):
        return map_coordinates(field,((xyz-self.origin)/self.dx-.5).T,order=1,mode='constant',cval=self.ambient if field is None else 0.)

    def temperature_at(self,xyz):
        q=((xyz-self.origin)/self.dx-.5).T
        return map_coordinates(self.temperature,q,order=1,mode='constant',cval=self.ambient)

    def pressure_at(self,xyz):
        return map_coordinates(self.p,((xyz-self.origin)/self.dx-.5).T,order=1,mode='constant',cval=0.)

    def deposit(self,grid,xyz,amount):
        xyz=np.array(xyz,copy=True)
        xyz[:,2]=np.maximum(xyz[:,2],self.origin[2]+self.dx*.5)
        ij=np.floor((xyz-self.origin)/self.dx).astype(int)
        valid=(ij>=0).all(1)&(ij<np.array(self.shape)).all(1)
        if np.any(~valid & (abs(amount)>1e-12)):raise RuntimeError('Gas exchange lies outside the gas domain')
        np.add.at(grid,tuple(ij[valid].T),amount[valid])

    def add_surface_heat(self,xyz,joules):
        self.deposit(self.pending_heat,xyz,joules);self.ledger['heat_in']+=float(np.sum(joules))

    def add_vapor(self,xyz,kg,temperature):
        self.deposit(self.pending_vapor,xyz,kg)
        # Latent enthalpy remains in the transported vapor inventory. Only
        # sensible gas enthalpy creates thermal expansion before condensation.
        sensible=kg*self.cp*temperature
        self.deposit(self.pending_heat,xyz,sensible)
        self.ledger['water_in']+=float(kg.sum());self.ledger['heat_in']+=float(sensible.sum())

    def add_fracture_dust(self,xyz,kg,specific_enthalpy,material):
        self.dust_material=material
        self.deposit(self.dust,xyz,kg);self.deposit(self.dust_h,xyz,kg*specific_enthalpy)
        self.ledger['dust_in']+=float(kg.sum());self.ledger['dust_enthalpy_in']+=float(np.sum(kg*specific_enthalpy))

    def volume_fraction(self,x,volume):
        q=(x-self.origin)/self.dx-.5;b=np.floor(q).astype(int);f=q-b;phi=np.zeros(self.shape)
        for i in (0,1):
            for j in (0,1):
                for k in (0,1):
                    ij=b+[i,j,k];valid=(ij>=0).all(1)&(ij<np.array(self.shape)).all(1)
                    w=(f[:,0] if i else 1-f[:,0])*(f[:,1] if j else 1-f[:,1])*(f[:,2] if k else 1-f[:,2])*volume/self.dx**3
                    np.add.at(phi,tuple(ij[valid].T),w[valid])
        # A regularized immersed interface. The residual porosity avoids
        # singular vanishing cut cells and is reported as a model limitation.
        return 1-np.minimum(gaussian_filter(phi,.5),.98)

    def initialize_material(self,x,volume):
        self.alpha=self.volume_fraction(x,volume)
        self.mass=self.rho0*self.alpha*self.dx**3;self.vapor=self.mass*.008
        self.initial_mass=float(self.mass.sum());self.initial_water=float(self.vapor.sum())

    def faces(self,c):
        result=[]
        for axis in range(3):
            shape=list(c.shape);shape[axis]+=1;f=np.empty(shape);sl=[slice(None)]*3;sl[axis]=slice(1,-1)
            f[tuple(sl)]=(np.take(c,range(c.shape[axis]-1),axis)+np.take(c,range(1,c.shape[axis]),axis))*.5
            sl[axis]=0;f[tuple(sl)]=np.take(c,0,axis);sl[axis]=-1;f[tuple(sl)]=np.take(c,-1,axis)
            result.append(f)
        return result

    def divergence(self,flux):
        return sum(np.diff(f,axis=a)/self.dx for a,f in enumerate(flux))

    def project(self,predicted,alpha,source,dt):
        rho=self.mass/(np.maximum(alpha,.02)*self.dx**3);beta=self.faces(1/np.maximum(rho,.05*self.rho0));af=self.faces(alpha)
        coeff=[dt*a*b for a,b in zip(af,beta)];index=np.arange(np.prod(self.shape)).reshape(self.shape)
        rows=[];cols=[];data=[];diagonal=np.zeros(self.shape)
        for axis in range(3):
            sa=[slice(None)]*3;sb=sa.copy();sf=sa.copy();sa[axis]=slice(None,-1);sb[axis]=slice(1,None);sf[axis]=slice(1,-1)
            a=index[tuple(sa)].ravel();b=index[tuple(sb)].ravel();c=coeff[axis][tuple(sf)].ravel()/self.dx**2
            rows.extend([a,b]);cols.extend([b,a]);data.extend([-c,-c]);diagonal[tuple(sa)]+=c.reshape(diagonal[tuple(sa)].shape);diagonal[tuple(sb)]+=c.reshape(diagonal[tuple(sb)].shape)
            # Open pressure boundaries; the bottom is a closed substrate.
            for end in (0,-1):
                if axis==2 and end==0:predicted[axis][:,:,0]=0;continue
                ss=[slice(None)]*3;ss[axis]=end
                diagonal[tuple(ss)]+=2*coeff[axis][tuple(ss)]/self.dx**2
        rows.append(index.ravel());cols.append(index.ravel());data.append(diagonal.ravel())
        A=coo_matrix((np.concatenate(data),(np.concatenate(rows),np.concatenate(cols))),shape=(index.size,)*2).tocsr()
        flux=[a*u for a,u in zip(af,predicted)];rhs=source-self.divergence(flux)
        # A=-div(dt*alpha/rho*grad). This sign makes the projected flux
        # satisfy the thermodynamic expansion constraint.
        p,info=cg(A,rhs.ravel(),x0=self.p.ravel(),M=diags(1/diagonal.ravel()),rtol=2e-8,atol=1e-10,maxiter=500)
        if info:raise RuntimeError(('Gas pressure solve failed',info))
        self.p=p.reshape(self.shape)
        for axis in range(3):
            sf=[slice(None)]*3;sf[axis]=slice(1,-1)
            flux[axis][tuple(sf)]-=coeff[axis][tuple(sf)]*np.diff(self.p,axis=axis)/self.dx
            for end in (0,-1):
                sf[axis]=end
                if axis==2 and end==0:flux[axis][tuple(sf)]=0;continue
                grad=(1 if end==0 else -1)*np.take(self.p,end,axis)*2/self.dx
                flux[axis][tuple(sf)]-=coeff[axis][tuple(sf)]*grad
        residual=float(np.max(abs(self.divergence(flux)-source)))
        self.vel=[q/np.maximum(a,.02) for q,a in zip(flux,af)]
        return flux,residual

    def transport(self,amount,flux,alpha,dt,ambient_density):
        density=amount/(np.maximum(alpha,.02)*self.dx**3);ff=[]
        for axis in range(3):
            pad=[(0,0)]*3;pad[axis]=(1,1);d=np.pad(density,pad,constant_values=ambient_density)
            left=np.take(d,range(d.shape[axis]-1),axis);right=np.take(d,range(1,d.shape[axis]),axis)
            ff.append(flux[axis]*np.where(flux[axis]>=0,left,right))
        change=-dt*self.divergence(ff)*self.dx**3
        result=amount+change
        if result.min() < -1e-12:raise RuntimeError('Gas transport positivity/CFL failure')
        return np.maximum(result,0),float(-change.sum())

    def implicit_transport(self,amounts,flux,alpha,dt,ambient,nonnegative=None):
        """Conservative, positive backward-Euler upwind transport.

        Boundary flux is measured independently from the updated density.
        This permits a moderate gas Courant number without unbounded losses.
        """
        index=np.arange(np.prod(self.shape)).reshape(self.shape);diag=(alpha*self.dx**3).ravel().copy()
        rows=[];cols=[];values=[];rhs=np.column_stack([q.ravel() for q in amounts])
        for axis,f in enumerate(flux):
            sa=[slice(None)]*3;sb=sa.copy();sf=sa.copy();sa[axis]=slice(None,-1);sb[axis]=slice(1,None);sf[axis]=slice(1,-1)
            a=index[tuple(sa)].ravel();b=index[tuple(sb)].ravel();q=f[tuple(sf)].ravel()*dt*self.dx**2
            positive=np.maximum(q,0);negative=np.maximum(-q,0)
            np.add.at(diag,a,positive);np.add.at(diag,b,negative)
            rows.extend([b,a]);cols.extend([a,b]);values.extend([-positive,-negative])
            for end in (0,-1):
                sl=[slice(None)]*3;sl[axis]=end;i=index[tuple(sl)].ravel();q=f[tuple(sl)].ravel()*dt*self.dx**2*(-1 if end==0 else 1)
                np.add.at(diag,i,np.maximum(q,0))
                rhs[i]+=np.maximum(-q,0)[:,None]*np.array(ambient)[None,:]
        rows.append(index.ravel());cols.append(index.ravel());values.append(diag)
        A=coo_matrix((np.concatenate(values),(np.concatenate(rows),np.concatenate(cols))),shape=(index.size,)*2).tocsc()
        density=splu(A).solve(rhs);result=[(density[:,i]*(alpha*self.dx**3).ravel()).reshape(self.shape) for i in range(len(amounts))]
        nonnegative=list(range(len(amounts))) if nonnegative is None else nonnegative
        if density[:,nonnegative].min()<-1e-10:raise RuntimeError('Implicit gas transport lost positivity')
        out=np.zeros(len(amounts))
        for axis,f in enumerate(flux):
            for end in (0,-1):
                sl=[slice(None)]*3;sl[axis]=end;i=index[tuple(sl)].ravel();q=f[tuple(sl)].ravel()*dt*self.dx**2*(-1 if end==0 else 1)
                out+=(np.maximum(q,0)[:,None]*density[i]-np.maximum(-q,0)[:,None]*np.array(ambient)[None,:]).sum(0)
        for i in range(len(amounts)):
            error=abs(result[i].sum()+out[i]-amounts[i].sum())
            if error>1e-10:raise RuntimeError(('Gas boundary flux balance failed',error))
        return result,out

    def advance(self,dt,material_x=None,material_volume=None):
        old_alpha=self.alpha.copy();target=self.alpha.copy() if material_x is None else self.volume_fraction(material_x,material_volume)
        heat=self.pending_heat.copy();vapor=self.pending_vapor.copy();self.pending_heat[:]=0;self.pending_vapor[:]=0
        speed=max(float(abs(v).max()) for v in self.vel)
        hot_estimate=self.temperature+np.maximum(heat,0)/(np.maximum(self.mass,1e-30)*self.cp)
        acceleration=9.81*float(np.max(abs(hot_estimate/self.ambient-1)))
        # Apply the acceleration bound to each proposed gas substep, not to
        # the entire material step; the latter oversubdivides steady plumes.
        courant_distance=.75*self.dx
        substep_bound=2*courant_distance/max(speed+np.sqrt(speed*speed+2*acceleration*courant_distance),1e-12)
        # Both advection and local expansion impose positivity limits.
        expansion=float(np.max(abs(heat)/(self.H*old_alpha*self.dx**3)))
        substeps=max(1,int(np.ceil(dt/substep_bound)),int(np.ceil(expansion/.10)))
        if substeps>400:raise RuntimeError(('Gas coupling timestep too large',substeps))
        subdt=dt/substeps;max_res=0
        for sub in range(substeps):
            prev=self.alpha.copy();self.alpha=old_alpha+(target-old_alpha)*(sub+1)/substeps
            temp=self.temperature
            centers=[(np.take(v,range(v.shape[a]-1),a)+np.take(v,range(1,v.shape[a]),a))*.5 for a,v in enumerate(self.vel)]
            predicted=[]
            for axis,v in enumerate(self.vel):
                coord=self.face_coords[axis];vel=np.array([map_coordinates(c,coord-.5,order=1,mode='nearest') for c in centers])
                offset=np.array([0 if i==axis else .5 for i in range(3)])[:,None,None,None]
                advected=map_coordinates(v,coord-subdt*vel/self.dx-offset,order=1,mode='constant',cval=0.)
                predicted.append(advected)
            rho=self.mass/(self.alpha*self.dx**3)
            buoyancy=9.81*(self.rho0-rho-self.dust/(self.alpha*self.dx**3))/np.maximum(rho,.05*self.rho0)
            predicted[2]+=subdt*self.faces(buoyancy)[2]
            # Conservative Fourier conduction with ambient exterior values.
            conduction=[]
            for axis,af in enumerate(self.faces(self.alpha)):
                pad=[(0,0)]*3;pad[axis]=(1,1);padded=np.pad(temp,pad,constant_values=self.ambient)
                f=self.conductivity*af*np.diff(padded,axis=axis)/self.dx
                for end in (0,-1):
                    sl=[slice(None)]*3;sl[axis]=end;f[tuple(sl)]*=2
                conduction.append(f)
            q_conduction=subdt*self.divergence(conduction)*self.dx**3
            self.ledger['conduction_out']-=float(q_conduction.sum())
            # Micrometre dust thermally relaxes toward the surrounding gas.
            # Its enthalpy is transported separately, including latent heat.
            tau=self.dust_material.density*self.dust_material.cp*self.dust_radius**2/(3*self.conductivity)
            dust_heat=(self.dust_h-self.dust*self.dust_material.enthalpy(temp))*(1-np.exp(-subdt/tau))
            self.dust_h-=dust_heat;self.ledger['dust_heat_to_air']+=float(dust_heat.sum())
            q=heat/substeps+q_conduction+dust_heat
            source=q/(self.H*self.dx**3*subdt)-(self.alpha-prev)/subdt
            flux,res=self.project(predicted,self.alpha,source,subdt);max_res=max(max_res,res)
            self.mass+=vapor/substeps;self.vapor+=vapor/substeps
            transported,out=self.implicit_transport([self.mass,self.vapor,self.liquid],flux,self.alpha,subdt,[self.rho0,self.rho0*.008,0.])
            self.mass,self.vapor,self.liquid=transported;self.ledger['mass_out']+=out[0];water_out,drop_out=out[1:]
            if np.any(self.dust):
                # Stokes terminal slip for fine basalt dust; no prescribed
                # plume trajectory or particle-size animation.
                settling=2*(self.dust_material.density-self.rho0)*9.81*self.dust_radius**2/(9*self.air_viscosity)
                dust_flux=[f.copy() for f in flux];dust_flux[2]-=settling*self.faces(self.alpha)[2];dust_flux[2][:,:,0]=0
                moved,dust_out=self.implicit_transport([self.dust,self.dust_h],dust_flux,self.alpha,subdt,[0.,0.],nonnegative=[0])
                self.dust,self.dust_h=moved;self.ledger['dust_out']+=dust_out[0];self.ledger['dust_enthalpy_out']+=dust_out[1]
            self.ledger['water_out']+=water_out+drop_out
            # The outgoing sensible enthalpy is fixed by the same projected
            # flux; expansion and boundary energy use the same discrete div.
            self.ledger['heat_out']+=float(subdt*self.H*self.divergence(flux).sum()*self.dx**3)
            self.time+=subdt
        mass_error=float(self.mass.sum()+self.ledger['mass_out']-self.initial_mass-self.ledger['water_in'])
        water_error=float(self.vapor.sum()+self.liquid.sum()+self.ledger['water_out']-self.initial_water-self.ledger['water_in'])
        dust_error=float(self.dust.sum()+self.ledger['dust_out']-self.ledger['dust_in'])
        dust_heat_error=float(self.dust_h.sum()+self.ledger['dust_enthalpy_out']+self.ledger['dust_heat_to_air']-self.ledger['dust_enthalpy_in'])
        row=dict(time=self.time,substeps=substeps,maxProjectionResidual=max_res,massErrorKg=mass_error,waterErrorKg=water_error,
                 temperatureRange=[float(self.temperature.min()),float(self.temperature.max())],maximumSpeed=max(float(abs(v).max()) for v in self.vel),dustMassErrorKg=dust_error,dustHeatErrorJ=dust_heat_error,dustMassKg=float(self.dust.sum()))
        if max(abs(mass_error),abs(water_error),abs(dust_error))>1e-8 or abs(dust_heat_error)>1e-6:raise RuntimeError(('Gas mass/enthalpy ledger failed',row))
        self.rows.append(row);return row

    def save(self,path):
        np.savez_compressed(path,mass=self.mass,vapor=self.vapor,liquid=self.liquid,alpha=self.alpha,pressure=self.p,u=self.vel[0],v=self.vel[1],w=self.vel[2],temperature=self.temperature,origin=self.origin,dx=self.dx,time=self.time,
                            dust=self.dust,dust_h=self.dust_h,density=self.dust/self.dx**3*3/(2*self.dust_material.density*self.dust_radius),extent=np.array(self.shape)*self.dx,
                            meta=json.dumps(dict(ledger=self.ledger,initial_mass=self.initial_mass,initial_water=self.initial_water,rows=self.rows)))

    @classmethod
    def load(cls,path):
        s=np.load(path);obj=cls(origin=s['origin'],shape=s['mass'].shape,dx=float(s['dx']))
        for k in ('mass','vapor','liquid','alpha'):setattr(obj,k,s[k].copy())
        for k in ('dust','dust_h'):
            if k in s:setattr(obj,k,s[k].copy())
        obj.p=s['pressure'].copy();obj.vel=[s[k].copy() for k in ('u','v','w')];obj.time=float(s['time'])
        meta=json.loads(str(s['meta']))
        defaults=obj.ledger.copy()
        for k in ('ledger','initial_mass','initial_water','rows'):setattr(obj,k,meta[k])
        obj.ledger={**defaults,**obj.ledger}
        return obj
