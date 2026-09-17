"""Initially molten lobe with a hot basal reservoir; CPU thermal fracture."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import argparse,hashlib,json,time,traceback
import numpy as np
from lava_mpm import ROOT,MPM,Material,block,SOURCE_HASHES
from lava_mpm_continuous import HotBed

def initial(refine,vertical=1):
    sample=np.array([.001,.001,.00025*vertical])/refine;cell=sample*2
    x=block([-.008,-.005,0],[.008,.005,.006],sample)
    x=x[(x[:,0]/.008)**2+(x[:,1]/.005)**2+(x[:,2]/.006)**2<1]
    origin=np.array([-.016,-.013,-.002]);high=np.array([.022,.013,.010]);shape=np.ceil((high-origin)/cell).astype(int)+1
    m=Material(rheology='basalt_power_creep',melt_viscosity_law='farrell_180719',fracture_length=.002)
    return MPM(x,sample[0],cell[0],temperature=1450.,material=m,cell_size=cell,sample_size=sample,origin=origin,shape=shape,gravity=(.855,0,-9.773),ground=True)

def run(name,until,dt,wall,refine,source=None,vertical=1):
    folder=ROOT/'rebuild-25'/name;folder.mkdir(exist_ok=True,parents=True)
    if (folder/'state.npz').exists():
        meta=json.loads((folder/'state.json').read_text())
        if meta.get('sourceHashes')!=SOURCE_HASHES:raise ValueError('Resume requires unchanged solver')
        s=MPM.load(folder)
    elif source is not None:
        parent=ROOT/'rebuild-25'/source;s=MPM.load(parent)
        if s.material.rheology!='basalt_power_creep':raise ValueError('Thermal continuation requires the same rock constitutive law')
        setup=json.loads((parent/'setup.json').read_text())
        setup['continuation']=dict(parentState=str(parent/'state.npz'),parentStateSha256=hashlib.sha256((parent/'state.npz').read_bytes()).hexdigest(),parentSourceHashes=json.loads((parent/'state.json').read_text()).get('sourceHashes'),startTime=s.time,change='Equivalent sparse elimination of pressure before Coulomb friction. Constitutive equations and state are unchanged.',sourceHashes=SOURCE_HASHES)
        (folder/'setup.json').write_text(json.dumps(setup,indent=2));s.save(folder/f'frame-{round(s.time*1000):04d}')
    else:
        s=initial(refine,vertical);s.save(folder/'frame-0000')
        (folder/'setup.json').write_text(json.dumps(dict(sceneKind='natural_lava_flow',initialCondition='Single initially molten half-ellipsoid, 16 x 10 x 6 mm, 1450 K, zero velocity, no cracks or damage.',bed='Metered 1450 K hot reservoir',gravity=s.gravity.tolist(),materialReferences='Farrell 2020 dry melt plus Violay 2012 glass-free rock creep. Constitutive reference mixture, not one composition calibrated across all phases.',sourceHashes=SOURCE_HASHES),indent=2))
    bed=HotBed(1450.);start=time.monotonic();error=None;next_frame=(np.floor(s.time/2)+1)*2;count=0
    try:
        while s.time<until-1e-9:
            cfl=np.max(np.sum(abs(s.v)/s.cell_size,axis=1));gradient=np.linalg.norm(s.C,axis=(1,2)).max()
            step=min(dt,.2/max(cfl,1e-9),.15/max(gradient,1e-9),until-s.time,next_frame-s.time)
            while True:
                s._solve_deadline=start+wall
                try:row=s.step(step,bed=bed);break
                except RuntimeError:
                    step*=.5
                    if step<1e-7:raise
                    if time.monotonic()>start+wall:raise TimeoutError('CPU thermal screening budget reached')
            count+=1
            if s.time>=next_frame-1e-9:
                dest=folder/f'frame-{round(s.time*1000):04d}';s.save(dest);next_frame+=2
                print(json.dumps(dict(time=s.time,temperature=row['temperatureRange'],coherent=int(s.connectivity.frozen.sum()),damage=float(s.damage.max()),brokenEdges=int(s.connectivity.broken.sum()),speed=row['maximumSpeed'],wallSeconds=time.monotonic()-start)),flush=True)
            if time.monotonic()>start+wall:raise TimeoutError('CPU thermal screening budget reached')
    except Exception as exc:
        error=str(exc);(folder/'failure-trace.txt').write_text(traceback.format_exc())
    s.save(folder);s.save(folder/f'frame-{round(s.time*1000):04d}')
    result=dict(status='pass' if error is None else 'incomplete',error=error,time=s.time,targetTime=until,steps=count,particles=len(s.x),temperatureRange=s.material.temperature(s.h)[[np.argmin(s.h),np.argmax(s.h)]].tolist(),maximumDamage=float(s.damage.max()),brokenEdges=int(s.connectivity.broken.sum()),coherentParticles=int(s.connectivity.frozen.sum()),maximumDeformationCondition=float(np.linalg.cond(s.F).max()),thermalBalanceRelative=s.rows[-1]['thermalBalanceRelative'] if s.rows else 0,wallSeconds=time.monotonic()-start,sourceHashes=SOURCE_HASHES,
        limits='CPU physical screening case; no spatial convergence or final appearance claim.')
    (folder/'proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='thermal-rock');p.add_argument('--until',type=float,default=20.);p.add_argument('--dt',type=float,default=.25);p.add_argument('--wall',type=float,default=120.);p.add_argument('--refine',type=int,default=1);p.add_argument('--source');p.add_argument('--vertical',type=float,default=1);a=p.parse_args();result=run(a.name,a.until,a.dt,a.wall,a.refine,a.source,a.vertical)
    raise SystemExit(0 if result['status']=='pass' else 2)
