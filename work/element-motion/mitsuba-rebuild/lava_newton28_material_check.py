"""CPU checks for phase stiffness, stress convention and fracture work."""
import os
from pathlib import Path
ROOT=Path(__file__).parent/'lava-focus/mpm/rebuild-28'
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',TEMP=str(ROOT/'compiler-temp'),TMP=str(ROOT/'compiler-temp'))
import json,numpy as np,warp as wp
from lava_newton28_thermal import update_material,plastic_damage
wp.config.kernel_cache_dir=str(ROOT/'warp-cache')


def enthalpy(t):return 1200*(t-1173.15)+400000*np.clip((t-1173.15)/250,0,1)


def run():
    wp.init()
    with wp.ScopedDevice('cpu'):
        t=np.array([1450.,1260.,1230.,1200.,1000.],dtype='f4');n=len(t)
        old=wp.array(enthalpy(np.full(n,1450.)),dtype=float);new=wp.array(enthalpy(t),dtype=float)
        d=wp.zeros(n);strength=wp.ones(n);f=np.tile(np.diag([1.0001,.9999,1.]),(n,1,1)).astype('f4');F=wp.array(f,dtype=wp.mat33)
        E=wp.full(n,1.2e9);nu=wp.full(n,.49);outputs=[wp.zeros(n) for _ in range(5)]
        wp.launch(update_material,n,inputs=[old,new,d,strength,F,E,nu,*outputs,1])
        ee=E.numpy();nn=nu.numpy();bulk=ee/(3*(1-2*nn));mu=ee/(2*(1+nn))
        strain=F.numpy()-np.eye(3);trace=np.trace(strain,axis1=1,axis2=2);dev=strain-trace[:,None,None]/3*np.eye(3)
        shear=2*mu[:,None,None]*dev
        expected=2*(1.2e9/(2*1.49))*(f-np.eye(3))
        relative=float(np.max(abs(shear-expected))/np.max(abs(expected)))
        n=3;I=np.tile(np.eye(3),(n,1,1)).astype('f4');g=np.zeros_like(I);sig=np.zeros_like(I)
        g[0,0,0]=.1;g[1,0,0]=-.1;sig[0,0,0]=-8e6;sig[1,0,0]=8e6
        H=wp.array(enthalpy(np.full(n,1000.)),dtype=float);damage=wp.zeros(n);plastic=wp.zeros(n);heat=wp.zeros(n);fracture=wp.zeros(n)
        wp.launch(plastic_damage,n,inputs=[wp.array(I,dtype=wp.mat33),wp.array(I,dtype=wp.mat33),wp.array(g,dtype=wp.mat33),wp.array(sig,dtype=wp.mat33),H,wp.ones(n),damage,plastic,.01,.003,heat,fracture])
        measured=damage.numpy();exact=1-np.exp(-.001/(100/(8e6*.003)))
        accounted=heat.numpy()*2700+fracture.numpy()
        checks=dict(bulk=bool(np.max(abs(bulk/20e9-1))<1e-4),deviatoricStress=relative<.01,tensionDamage=abs(float(measured[0])-exact)<2e-5,compressionIntact=measured[1]==0,restIntact=measured[2]==0,plasticWork=bool(np.max(abs(accounted-np.array([8000,8000,0])))<1.))
        checks={k:bool(v) for k,v in checks.items()}
        report=dict(status='pass' if all(checks.values()) else 'fail',device='CPU',checks=checks,bulkModuliPa=bulk.tolist(),stressRelativeError=relative,tensileDamage=float(measured[0]),analyticDamage=float(exact),accountedPlasticWorkPerM3=accounted.tolist())
        (ROOT/'material-cpu.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True);assert report['status']=='pass'

if __name__=='__main__':run()
