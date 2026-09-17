"""CPU tests for the independent gas solver and lava/gas exchange."""
import json,time,traceback
import numpy as np
from lava_mpm_gas import Gas
from lava_mpm import ROOT,MPM,block


def still_air():
    g=Gas(shape=(8,8,12),origin=(-.04,-.04,0),dx=.01)
    row=g.advance(.05)
    assert row['maximumSpeed']<1e-9 and max(abs(g.temperature-293.15).ravel())<1e-8
    return row


def heat_plume():
    g=Gas(shape=(10,10,16),origin=(-.05,-.05,0),dx=.01)
    g.add_surface_heat(np.array([[0,0,.025]]),np.array([.025]))
    rows=[]
    for _ in range(8):rows.append(g.advance(.01))
    assert g.temperature.max()>294 and g.vel[2].max()>0
    assert max(abs(r['massErrorKg']) for r in rows)<1e-10
    return dict(final=rows[-1],ledger=g.ledger)


def displaced_air():
    g=Gas(shape=(10,10,16),origin=(-.05,-.05,0),dx=.01)
    x=block([-.015,-.015,0],[.015,.015,.02],.005);vol=np.full(len(x),.005**3)
    g.initialize_material(x,vol);old=float(g.alpha.sum())
    row=g.advance(.02,x+np.array([.001,0,0]),vol)
    assert abs(row['massErrorKg'])<1e-10
    return dict(final=row,fluidVolumeChangeM3=float((g.alpha.sum()-old)*g.dx**3))


def thermal_exchange():
    g=Gas(shape=(12,12,16),origin=(-.06,-.06,0),dx=.01)
    x=block([-.015,-.015,.005],[.015,.015,.025],.01)
    s=MPM(x,.01,.02,temperature=1450,origin=[-.08,-.08,-.04],shape=[10,10,12],gravity=(0,0,0),ground=True)
    g.initialize_material(s.x,s.volume)
    row=s.step(.02,gas=g);gasrow=g.advance(.02,s.x,s.volume)
    mismatch=abs(s.ledger['convection']-g.ledger['heat_in'])
    assert mismatch<1e-10 and g.temperature.max()>293.15
    return dict(exchangeMismatchJ=mismatch,material=row,gas=gasrow)


def fracture_dust():
    from lava_mpm import Material
    g=Gas(shape=(8,8,12),origin=(-.04,-.04,0),dx=.01);m=Material()
    source_mass=np.array([1e-8]);source_h=np.array([float(m.enthalpy(1100.))])
    g.add_fracture_dust(np.array([[0,0,.03]]),source_mass,source_h,m)
    for _ in range(5):r=g.advance(.01)
    assert abs(r['dustMassErrorKg'])<1e-14 and abs(r['dustHeatErrorJ'])<1e-9
    assert g.ledger['dust_heat_to_air']>0 and g.temperature.max()>293.15
    return dict(final=r,ledger=g.ledger)


if __name__=='__main__':
    out=ROOT/'validation';out.mkdir(parents=True,exist_ok=True);failed=False
    for name,fn in [('gas_still_air',still_air),('gas_heat_plume',heat_plume),('gas_displacement',displaced_air),('gas_thermal_exchange',thermal_exchange),('gas_fracture_dust',fracture_dust)]:
        start=time.time()
        try:r=dict(status='pass',evidence=fn())
        except Exception as e:r=dict(status='fail',error=str(e),traceback=traceback.format_exc());failed=True
        r['seconds']=time.time()-start;(out/f'{name}.json').write_text(json.dumps(r,indent=2));print(name,r['status'],str(r.get('error',''))[:400],flush=True)
    if failed:raise SystemExit(1)
