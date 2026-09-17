"""Particle enthalpy, surface radiation and thermal rest-strain for Newton MPM.

Brookshaw SPH conduction uses symmetric pair fluxes. Surface area is obtained
from the particle occupancy gradient, not a painted temperature mask. All
initial particles are hot, intact material. This is a declared hybrid model;
the local crack-band softening is not the earlier variational AT2 solver.
"""
import warp as wp


@wp.func
def temperature(h:float):
    if h<0.0:return 1173.15+h/1200.0
    if h<700000.0:return 1173.15+h/2800.0
    return 1423.15+(h-700000.0)/1200.0


@wp.func
def enthalpy(t:float):
    return 1200.0*(t-1173.15)+400000.0*wp.clamp((t-1173.15)/250.0,0.0,1.0)


@wp.func
def coherence(t:float):
    phi=wp.clamp((1423.15-t)/250.0,0.0,1.0)
    return wp.clamp((phi-0.60)/0.35,0.0,1.0)


@wp.func
def dkernel(r:float,h:float):
    q=r/h
    a=1.0/(wp.pi*h*h*h*h)
    if q<1.0:return a*(-3.0*q+2.25*q*q)
    if q<2.0:return -0.75*a*(2.0-q)*(2.0-q)
    return 0.0


@wp.kernel
def heat_step(x:wp.array[wp.vec3],hin:wp.array[float],hout:wp.array[float],grid:wp.uint64,
              pitch:float,k:float,emissivity:float,convection:float,ambient:float,
              bed_temperature:float,dt:float,bed_enabled:int,
              area:wp.array[float],loss:wp.array[float],conduction:wp.array[float]):
    i=wp.tid();p=x[i];ti=temperature(hin[i]);vol=pitch*pitch*pitch;mass=2700.0*vol;h=1.3*pitch
    grad=wp.vec3(0.0);dh=float(0.0)
    for j in wp.hash_grid_query(grid,p,2.0*h):
        rvec=p-x[j];r=wp.length(rvec)
        if r>pitch*0.01 and r<2.0*h:
            deriv=dkernel(r,h)
            grad+=vol*deriv*rvec/r
            conductance=-2.0*k*vol/2700.0*deriv*r/(r*r+0.01*h*h)
            dh+=conductance*(temperature(hin[j])-ti)
    outward=-grad;g=wp.length(outward)
    exposed=2.0*vol*g
    bottom=float(0.0)
    if bed_enabled==1 and p[2]<2.0*h:
        bottom=2.0*vol*wp.max(0.0,-outward[2]);exposed=wp.max(0.0,exposed-bottom)
    power=exposed*(emissivity*5.670374419e-8*(ti*ti*ti*ti-ambient*ambient*ambient*ambient)+convection*(ti-ambient))
    # Semi-infinite hot basalt substrate is an explicit thermal reservoir.
    # Its exchange is recorded separately through the same energy ledger.
    power+=bottom*k*(ti-bed_temperature)/(2.0*h)
    hout[i]=hin[i]+dt*(dh-power/mass)
    area[i]=exposed;loss[i]=power*dt;conduction[i]=mass*dh*dt


@wp.kernel
def update_material(hin:wp.array[float],hout:wp.array[float],damage:wp.array[float],strength:wp.array[float],
                    elastic:wp.array[wp.mat33],E:wp.array[float],nu:wp.array[float],eta:wp.array[float],
                    yieldp:wp.array[float],tensile:wp.array[float],shear:wp.array[float],friction:wp.array[float],track_strain:int):
    i=wp.tid();old_t=temperature(hin[i]);t=temperature(hout[i]);c=coherence(t);old_c=coherence(old_t)
    # Multiplicative thermal rest strain, applied before the mechanical solve.
    # Cooling produces tensile elastic strain only where a skeleton exists.
    thermal_scale=wp.exp(-8.0e-6*(t-old_t)*wp.min(old_c,c))
    intact=wp.max(0.0001,1.0-damage[i])
    # Preserve the same 20 GPa bulk modulus across phase change. Blending
    # E and nu independently had abruptly changed pressure compliance.
    old_mu=E[i]/(2.0*(1.0+nu[i]))
    mu_fluid=1.2e9/(2.0*1.49)
    mu=mu_fluid+(12.0e9-mu_fluid)*c*c*c
    bulk=20.0e9
    if track_strain==1:
        U,stretch,V=wp.svd3(elastic[i])
        mean=(stretch[0]+stretch[1]+stretch[2])/3.0
        ratio=old_mu/mu
        remapped=wp.vec3(mean+ratio*(stretch[0]-mean),mean+ratio*(stretch[1]-mean),mean+ratio*(stretch[2]-mean))
        elastic[i]=(U@wp.diag(remapped)@wp.transpose(V))*thermal_scale
    E[i]=9.0*bulk*mu/(3.0*bulk+mu)
    nu[i]=(3.0*bulk-2.0*mu)/(2.0*(3.0*bulk+mu))
    phi=wp.clamp((1423.15-t)/250.0,0.0,1.0)
    # VFT melt relation is evaluated only within its mobile melt range.
    melt_t=wp.max(t,1260.65)
    melt=wp.pow(10.0,-4.55+5978.4/(melt_t-595.3))
    suspension=wp.pow(wp.max(0.08,1.0-phi/0.65),-1.625)
    eta[i]=melt*suspension*(1.0-c)+150.0*c
    yieldp[i]=1.0e9
    ft=8.0e6*c*c*c*strength[i]
    tensile[i]=ft*intact/yieldp[i]
    shear[i]=ft*intact
    friction[i]=0.6*c


@wp.kernel
def plastic_damage(oldF:wp.array[wp.mat33],newF:wp.array[wp.mat33],grad:wp.array[wp.mat33],stress:wp.array[wp.mat33],
                   h:wp.array[float],strength:wp.array[float],damage:wp.array[float],plastic:wp.array[float],
                   dt:float,band:float,plastic_heat:wp.array[float],fracture_density:wp.array[float]):
    i=wp.tid();c=coherence(temperature(h[i]));I=wp.identity(n=3,dtype=float)
    lost=I+dt*grad[i]-newF[i]@wp.inverse(oldF[i])
    # Newton's rheology reaction tensor is compression-positive (its
    # tensile normal bound is negative). Convert to Cauchy tension-positive
    # convention for opening damage and positive plastic work.
    ep=0.5*(lost+wp.transpose(lost));sigma=-stress[i]
    Q,e=wp.eig3(ep);R,s=wp.eig3(sigma)
    opening=wp.max(0.0,wp.max(e[0],wp.max(e[1],e[2])))
    tension=wp.max(s[0],wp.max(s[1],s[2]))
    ft=8.0e6*c*c*c*strength[i]
    surface_work=float(0.0)
    if c>0.1 and tension>ft*wp.max(0.0001,1.0-damage[i])*0.5:
        plastic[i]+=opening
        # Crack-band energy regularization; Gc scales with skeleton fraction.
        gc=100.0*c*c
        failure_strain=gc/wp.max(ft*band,1.0e-8)
        increment=(1.0-damage[i])*(1.0-wp.exp(-opening/failure_strain))
        damage[i]=wp.min(0.99999,damage[i]+increment)
        surface_work=gc/band*increment
    dissipation=wp.max(0.0,wp.ddot(sigma,ep))
    surface_work=wp.min(surface_work,dissipation)
    heat=(dissipation-surface_work)/2700.0
    h[i]+=heat;plastic_heat[i]=heat;fracture_density[i]=surface_work


@wp.kernel
def diagnostic(h:wp.array[float],t:wp.array[float],c:wp.array[float]):
    i=wp.tid();t[i]=temperature(h[i]);c[i]=coherence(t[i])
