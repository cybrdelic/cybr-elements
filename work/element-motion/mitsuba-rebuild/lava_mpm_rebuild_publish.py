"""Publish measured CPU evidence at the existing lava repairs URL."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import json,shutil,hashlib
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from lava_mpm import ROOT,Material,SOURCE_HASHES


def main():
    folder=ROOT/'rebuild-24';root=Path(__file__).resolve().parents[3]
    public=root/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava/mpm/repairs';public.mkdir(parents=True,exist_ok=True)
    component=json.loads((folder/'component-validation.json').read_text());temporal=json.loads((folder/'short-temporal-validation.json').read_text())
    integration=json.loads((folder/'integration-validation.json').read_text())
    recovery=json.loads((folder/'softening-impulse-5/proof.json').read_text())
    source_current=component['sourceHashes']==SOURCE_HASHES and temporal['sourceHashes']==SOURCE_HASHES and integration['sourceHashes']==SOURCE_HASHES
    if not source_current:raise ValueError('Refusing to publish stale component/time evidence')
    tests=component['tests'];passed=sum(q['status']=='pass' for q in tests.values())+sum(q['status']=='pass' for q in integration['tests'].values())
    recovery['sourceHashes']=json.loads((folder/'softening-impulse-5/state.json').read_text()).get('sourceHashes')
    recovery['parentCache']='softening-impulse-4/state.npz'
    recovery['parentCacheSha256']=hashlib.sha256((folder/'softening-impulse-4/state.npz').read_bytes()).hexdigest()
    evidence=dict(sourceHashes=SOURCE_HASHES,componentValidation=component,integrationValidation=integration,shortTemporalValidation=temporal,experimentalRecovery=recovery,
        productionReady=False,fullFractureTemporal=dict(status='not demonstrated'),fullFractureSpatial=dict(status='not demonstrated'),
        naturalFlow=dict(status='not demonstrated'),materialCalibration=dict(status='nominal parameters; no composition-specific fit'),gpuUsed=False)
    (folder/'production-validation.json').write_text(json.dumps(evidence,indent=2))
    (public/'solver-review.json').write_text(json.dumps(evidence,indent=2))
    # Small standalone scientific figure, never an invented lava beauty frame.
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'text.color':'#d5cdc5','axes.labelcolor':'#b5aaa0','xtick.color':'#9c9187','ytick.color':'#9c9187','axes.edgecolor':'#514136','axes.facecolor':'#000','figure.facecolor':'#000','savefig.facecolor':'#000','grid.color':'#352b25'})
    fig,axes=plt.subplots(2,2,figsize=(14.4,8.4),dpi=100);fig.subplots_adjust(left=.075,right=.975,top=.89,bottom=.085,wspace=.25,hspace=.43)
    fig.suptitle('CYBRDELIC / LAVA — CPU SOLVER EVIDENCE',x=.075,ha='left',fontsize=18,color='#e3d6ca')
    m=Material();t=np.linspace(850,1320,300);mu,f,_,_=m.network(t,.001);tau=1/(mu*f)
    axes[0,0].semilogy(t,tau,color='#efac6c',lw=2);axes[0,0].set(xlabel='Temperature (K)',ylabel='Shear relaxation time (s)',title='Hot crust keeps creeping');axes[0,0].text(.04,.08,'Nominal material parameters; not a basalt fit',transform=axes[0,0].transAxes,color='#9c9187',fontsize=9)
    e=tests['phase']['details']['crackEnergyJPerM2'];axes[0,1].plot([2,4,8],e,'o-',color='#efac6c',lw=2);axes[0,1].axhline(100,color='#aaa',ls='--',lw=1);axes[0,1].set(xlabel='Samples per fracture length',ylabel='Fracture energy (J/m²)',title='Crack-energy functional approaches its analytic value');axes[0,1].text(.53,.80,'Target: 100 J/m²',transform=axes[0,1].transAxes,color='#aaa')
    dts=np.array([r['dt'] for r in temporal['runs']])*1000;work=np.array([r['boundaryWorkJ'] for r in temporal['runs']])*1e6
    axes[1,0].plot(dts,work,'o-',color='#efac6c',lw=2);axes[1,0].invert_xaxis();axes[1,0].set(xlabel='Maximum timestep (ms), decreasing →',ylabel='Loading work (µJ)',title='Short tensile test: three timestep levels');axes[1,0].text(.04,.08,'Work difference: 3.48% → 1.81%',transform=axes[1,0].transAxes,color='#aaa')
    state=json.loads((folder/'softening-impulse-5/state.json').read_text());rows=state['rows'];times=np.array([r['time'] for r in rows])*1000;damage=[r['maximumDamage'] for r in rows]
    axes[1,1].plot(times,damage,color='#efac6c',lw=2);axes[1,1].set(xlabel='Physical time (ms)',ylabel='Maximum damage',title='Strong softening: experimental continuation');axes[1,1].set_ylim(0,1);axes[1,1].text(.04,.08,'Final continuation only: local error controlled',transform=axes[1,1].transAxes,color='#aaa',fontsize=9)
    for ax in axes.flat:ax.grid(True,alpha=.55);ax.spines[['top','right']].set_visible(False)
    plot=folder/'solver-evidence.png';fig.savefig(plot);plt.close(fig);shutil.copy2(plot,public/'solver-evidence.png')
    shutil.copy2(folder/'surface.png',public/'surface-contract.png')
    old=public/'index.html';archive=public/'structure-23.html'
    if old.exists() and not archive.exists():shutil.copy2(old,archive)
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cybrdelic — lava solver rebuild</title><style>
*{box-sizing:border-box}body{margin:0;background:#000;color:#ded3c9;font:15px/1.6 system-ui}main{max-width:1240px;margin:auto;padding:26px 4% 64px}header{display:flex;justify-content:space-between;border-bottom:1px solid #32281f;padding-bottom:16px;font-size:11px;letter-spacing:.13em}a{color:#d8a478}h1{font-size:clamp(32px,5vw,56px);font-weight:450;letter-spacing:-.04em;line-height:1.12;margin:36px 0 18px}p{max-width:900px;color:#b8aca1}.notice{border-left:2px solid #b57c51;padding:10px 18px;margin:24px 0}figure{margin:28px 0}img{display:block;width:100%;height:auto;background:#000}figcaption{font-size:12px;color:#a39589;margin-top:10px}table{border-collapse:collapse;width:100%;margin:28px 0}td,th{text-align:left;padding:13px 10px;border-bottom:1px solid #32281f;vertical-align:top}th{font-weight:500}td{color:#b8aca1}details{margin:30px 0;border-top:1px solid #32281f;padding-top:20px}summary{cursor:pointer}footer{font-size:12px;color:#a39589} @media(max-width:640px){table{font-size:12px}td,th{padding:10px 5px}}
</style><main><header><span>CYBRDELIC / LAVA</span><a href="../">Lava studies</a></header><h1>The mechanics have been rebuilt.</h1><p>Continuous hot-crust creep, energy-based phase-field damage, implicit compression pressure, friction with heat accounting, and timestep rejection now have CPU tests. The surface path treats liquid and coherent crust separately.</p><p class="notice"><strong>Full lava breakup is still unverified. Rendering remains blocked.</strong><br>The short load test passes three timestep levels. Strong softening reaches approximately 95% damage in an experimental continuation, but this does not establish complete crack separation, spatial convergence or a natural lava flow. Material parameters remain nominal.</p><figure><img src="solver-evidence.png" width="1440" height="840" alt="Measured CPU curves for thermal creep, fracture energy, three timestep loading work values, and experimental damage evolution"><figcaption>Measured numerical evidence, not a new lava beauty render. The short test reaches about 25% damage; the strong-softening continuation uses an experimental transfer scheme.</figcaption></figure><table><thead><tr><th>Change</th><th>Verified</th><th>Still needed</th></tr></thead><tbody><tr><td>Temperature-dependent creep</td><td>Continuous packing transition and analytic Maxwell relaxation</td><td>Composition-specific calibration and crystallization kinetics</td></tr><tr><td>Phase-field fracture</td><td>Energy refinement, irreversibility, unloaded/compression behavior</td><td>Complete opening and independent full-fracture convergence</td></tr><tr><td>Implicit pressure and friction</td><td>Piston, stick/slip, rotated contacts, MPM collision, heat and momentum</td><td>Large fragment stacks and sparse scaling</td></tr><tr><td>Adaptive stepping</td><td>Rejected-state rollback and short three-level comparison</td><td>Long natural-flow convergence</td></tr><tr><td>Surface reconstruction</td><td>Crust and crack walls fixed; liquid fairing preserves volume</td><td>Large-deformation liquid remeshing and final appearance</td></tr></tbody></table><details><summary>Surface contract — CPU geometric test</summary><figure><img src="surface-contract.png" width="960" height="430" alt="Prescribed geometric fixture before and after liquid-only smoothing; the crust and crack walls are identical"><figcaption>This is an explicitly prescribed geometric test fixture. It proves preservation of cracks during surface processing; it is not simulated lava.</figcaption></figure></details><footer>CPU only · PASSED_COUNT component and regression checks passed · <a href="solver-review.json">Measured reports</a> · <a href="solver-method.md">Method and limits</a> · <a href="structure-23.html">Previous structure-23 diagnostics</a></footer></main></html>'''
    old.write_text(html.replace('PASSED_COUNT',str(passed)).replace('The mechanics have been rebuilt.','CPU solver rebuild.'),encoding='utf-8')
    method=Path(__file__).with_name('lava_mpm_rebuild.md').read_text()
    method+='\n\n## Current result\n\n'+str(passed)+' component/regression checks pass. The short tensile comparison passes, with work error decreasing from 3.483% to 1.813%. These are different cases from the historical structure-23 fracture, not a 157% to 1.8% rerun claim.\n\nStrong softening initially exposed per-remap APIC velocity filtering. The experimental affine impulse transfer has zero-time identity and a declared 1 ms filtering timescale. Its bounded continuation reaches about 95% damage; it remains experimental. No complete new lava video or photorealism is claimed.\n\nProduction remains blocked on complete fracture/time and spatial checks, calibrated rheology, large-deformation surfaces and a validated natural-flow scene.\n'
    (public/'solver-method.md').write_text(method,encoding='utf-8')
    print(json.dumps(dict(page=str(old),plot=str(plot),passed=passed,productionReady=False,imageSize=[1440,840],gpuUsed=False)))


if __name__=='__main__':main()
