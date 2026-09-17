"""Small CPU reference laws for testing material mechanisms before scene solves.

These functions deliberately do not import the GPU MPM code. They are reduced
constitutive models and benchmarks, not claims of a finished multiphysics sim.
"""
import numpy as np

def water_enthalpy_to_state(h,melting=273.15,latent=334000.,c_ice=2100.,c_water=4180.):
 h=np.asarray(h);temperature=np.where(h<0,melting+h/c_ice,np.where(h<=latent,melting,melting+(h-latent)/c_water));liquid=np.clip(h/latent,0,1);return temperature,1-liquid

def cooling_step(h,ambient,area_mass,dt):
 temperature,phase=water_enthalpy_to_state(h);loss=80*area_mass*(temperature-ambient);return h-loss*dt

def lava_viscosity(temperature,crystal_fraction):
 # Arrhenius temperature dependence with a packing divergence. Constants here
 # define a test basalt-like regime; they are not a calibrated lava sample.
 temperature=np.asarray(temperature);phi=np.asarray(crystal_fraction);return 80*np.exp(24000*(1/temperature-1/1450))*np.maximum(1-phi/.64,.03)**-2

def metal_return_map(log_stretch,plastic):
 eps=np.asarray(log_stretch);mean=eps.mean(axis=-1,keepdims=True);dev=eps-mean;norm=np.linalg.norm(dev,axis=-1);limit=.035+.05*plastic;excess=np.maximum(0,norm-limit);returned=mean+dev*np.minimum(1,limit/np.maximum(norm,1e-12))[...,None];return returned,np.minimum(1,plastic+excess*.4)

def snow_return_map(stretch,plastic_volume):
 stretch=np.asarray(stretch);projected=np.clip(stretch,.975,1.006);jp=np.clip(plastic_volume*np.prod(stretch,axis=-1)/np.prod(projected,axis=-1),.65,1.4);hardening=np.exp(np.clip(8*(1-jp),-2,3));return projected,jp,hardening

def mud_shear_rate(stress,yield_stress=38.,consistency=12.,n=.55):
 return np.sign(stress)*(np.maximum(np.abs(stress)-yield_stress,0)/consistency)**(1/n)

def blood_transmittance(thickness):
 # Beer-Lambert optical depth. RGB extinction is an art-directed absorption
 # approximation; not a biomedical spectral blood model.
 return np.exp(-np.asarray(thickness)[...,None]*np.array([38.,420.,560.]))

def drain_films(liquid,edges,height,dt,conductance=.08):
 liquid=np.asarray(liquid).copy();i,j=np.asarray(edges).T;potential=liquid+np.asarray(height)*.08;flow=(potential[i]-potential[j])*conductance*dt
 # Limit each donor's outgoing volume, so mass stays nonnegative even when
 # several junctions drain simultaneously.
 donor=np.where(flow>=0,i,j);receiver=np.where(flow>=0,j,i);amount=np.abs(flow);total=np.bincount(donor,weights=amount,minlength=len(liquid));amount*=np.minimum(1,liquid[donor]/np.maximum(total[donor],1e-12));np.add.at(liquid,donor,-amount);np.add.at(liquid,receiver,amount);return liquid

def leaf_step(angle,velocity,target,dt,stiffness=48.,damping=4.0):
 acceleration=stiffness*(target-angle)-damping*velocity;velocity+=acceleration*dt;return angle+velocity*dt,velocity

def local_exchange(a,b,weight):
 delta=(a-b)*np.clip(weight,0,.5);return a-delta,b+delta
