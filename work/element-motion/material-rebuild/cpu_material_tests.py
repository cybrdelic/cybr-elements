"""Cheap material-law and geometry checks; no beauty renders or GPU imports."""
from pathlib import Path
import sys,time,json,numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from cpu_material_models import *
from cpu_geometry import seal_boundaries,packed_surface_cells
from scipy.spatial import cKDTree
start=time.time();results=[]
def record(name,ok,evidence,scope):
 results.append({'test':name,'pass':bool(ok),'evidence':evidence,'scope':scope});assert ok,(name,evidence)
# Latent heat: temperature remains at melting while the solid fraction grows.
enthalpy=np.array([-21000.,0.,83500.,167000.,250500.,334000.,375800.]);temperature,solid=water_enthalpy_to_state(enthalpy)
record('ice_latent_heat',np.allclose(temperature[1:6],273.15) and np.all(np.diff(solid)<=0),{'temperatureK':temperature.tolist(),'solidFraction':solid.tolist()},'Reference law; scene coupling is separately reviewed')
h=np.full(64,375800.);history=[]
for step in range(600):h=cooling_step(h,253.15,.25,.1);history.append(float(h.mean()))
record('ice_monotonic_energy_loss',np.all(np.diff(history)<0),{'initialEnthalpy':375800.,'finalEnthalpy':history[-1]},'CPU thermal coupon')
mu=lava_viscosity(np.array([1450.,1350.,1250.]),np.array([0.,.2,.45]));record('lava_cooling_stiffens',np.all(np.diff(mu)>0),{'viscosityPaS':mu.tolist()},'Reference viscosity law; full feedback solve still required')
elastic,plastic=metal_return_map(np.array([[.006,-.003,-.003],[.18,-.09,-.09]]),np.zeros(2));record('metal_yield_and_permanent_state',plastic[0]==0 and plastic[1]>0 and np.linalg.norm(elastic[1])<.18,{'elasticLogStretch':elastic.tolist(),'plasticState':plastic.tolist()},'CPU return-map reference to cached MPM law')
for f in [30,45,65,90]:
 a=np.load(R.parent/'dynamics/surface/metal'/f'{f:04}.npz');ff=np.concatenate([a['f'][:,[0,1,2]],a['f'][:,[0,2,3]]]);v,ff,_,caps=seal_boundaries(a['v'],ff);ee=np.sort(np.concatenate([ff[:,[0,1]],ff[:,[1,2]],ff[:,[2,0]]]),axis=1);_,counts=np.unique(ee,axis=0,return_counts=True);volume=float(np.sum(v[ff[:,0]]*np.cross(v[ff[:,1]],v[ff[:,2]]))/6)
 record('metal_closed_surface_'+str(f),np.all(counts==2) and volume>0,{'caps':caps,'volume':volume,'boundaryEdges':int((counts==1).sum())},'Actual rendered mesh')
a=np.load(R/'data/foam/0045.npz');keep=packed_surface_cells(a['p'],a['r'],a['id']);p,r=a['p'][keep],a['r'][keep];dist,near=cKDTree(p).query(p,k=2);overlap=float((dist[:,1]/(r+r[near[:,1]])<.55).mean());record('foam_no_severe_overlap',overlap==0,{'inputCells':len(a['p']),'retainedCells':len(keep),'severeOverlapFraction':overlap},'Actual diagnostic reconstruction; temporal packing not certified')
water=np.array([1.,.8,.6,.4]);mass=water.sum();edges=np.array([[0,1],[1,2],[2,3]]);z=np.array([3.,2.,1.,0.])
for i in range(800):water=drain_films(water,edges,z,.01)
record('foam_drainage_mass',abs(water.sum()-mass)<1e-10 and np.min(water)>=0 and water[-1]>.4,{'initialMass':mass,'finalMass':float(water.sum()),'liquidAtNodes':water.tolist()},'CPU shared-film drainage coupon')
ss,jp,hard=snow_return_map(np.array([[.82,.82,.82],[1.,1.,1.]]),np.ones(2));record('snow_compaction_memory',jp[0]<jp[1] and hard[0]>hard[1],{'plasticVolume':jp.tolist(),'hardening':hard.tolist()},'CPU MPM material reference')
rates=mud_shear_rate(np.array([0.,20.,37.,40.,70.]));record('mud_yield_threshold',np.all(rates[:3]==0) and np.all(np.diff(rates[3:])>0),{'shearRates':rates.tolist()},'CPU yield-fluid coupon; existing movie carrier is not this solve')
trans=blood_transmittance(np.array([.001,.01,.08]));record('blood_thickness_absorption',np.all(np.diff(trans,axis=0)<0) and trans[-1,0]>trans[-1,1],{'RGBTransmission':trans.tolist()},'Optical law coupon')
angle=vel=0.;angles=[]
for i in range(480):angle,vel=leaf_step(angle,vel,.6 if i<120 else 0.,1/240);angles.append(angle)
record('leaf_lag_and_settle',angles[0]<.01 and abs(angles[-1])<.08,{'firstStep':angles[0],'peakAngle':max(angles),'finalAngle':angles[-1]},'CPU leaf attachment response')
a,b=local_exchange(np.array([1.,.1]),np.array([.2,.8]),.3);record('energy_local_exchange',np.allclose(a+b,[1.2,.9]),{'channelA':a.tolist(),'channelB':b.tolist()},'Designed fictional field with conserved exchange')
repair=json.loads((R/'cpu/identity/repair.json').read_text());areas=[x['missingArea'] for x in repair['frames']];record('healing_actual_gap_closure',np.all(np.diff(areas)<=1e-8) and areas[-1]<1e-8,{'missingAreas':areas},'Actual original-sigil geometry')
for kind in ['sound','pressure']:
 a=np.load(R/'cpu/witness'/f'{kind}.npz');info=json.loads((R/'cpu/witness'/f'{kind}.json').read_text());record(kind+'_finite_distinct_response',np.isfinite(a['p']).all() and info['CFL']<1/np.sqrt(2),info,'Actual CPU witness sequence')
for kind in ['sand','snow']:
 for f in [30,45,65,90]:
  a=np.load(R.parent/'dynamics/cache'/kind/f'{f:04}.npz');J=np.linalg.det(a['F'].astype('f4'));record(kind+'_positive_deformation_'+str(f),bool((J>0).all()),{'minimumJ':float(J.min()),'maximumJ':float(J.max())},'Existing dynamics cache, CPU validation')
report={'device':'CPU','seconds':round(time.time()-start,3),'passed':sum(x['pass'] for x in results),'tests':results,'interpretation':'Law coupons validate mechanisms, not complete scene coupling or photorealism.'};(R/'cpu/material-tests.json').write_text(json.dumps(report,indent=2));print('CPU material checks:',report['passed'],'passed in',report['seconds'],'seconds')
