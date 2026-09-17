"""Publish explicitly labelled progress evidence, never a final lava render."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,shutil
import numpy as np
from lava_mpm import ROOT

WORK=Path(__file__).resolve().parents[2]
DEST=WORK.parent/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava/mpm/repairs'

def build(active=()):
    runs=[]
    current='integrated-flow-10' if (ROOT/'rebuild-38/integrated-flow-10/state.json').exists() else 'integrated-flow'
    adaptive_case='adaptive-resume' if (ROOT/'rebuild-38/adaptive-resume/proof.json').exists() else 'adaptive-start'
    for name,label in [('hot-nozzle','Heated-floor control'),('fine-repaired','Finer-grid pressure test'),('finite-bed-continued','Rock heat-exchange test'),(current,'Corrected starting surface'),(adaptive_case,'Error-controlled startup / resume'),('validated-flow','Adaptive cooled-flow run')]:
        folder=ROOT/'rebuild-38'/name
        if not (folder/'state.json').exists():continue
        meta=json.loads((folder/'state.json').read_text());s=np.load(folder/'state.npz')
        if abs(float(s['time'])-meta['time'])>1e-10:raise RuntimeError('Progress checkpoint changed during read; retry')
        proof=json.loads((folder/'proof.json').read_text()) if (folder/'proof.json').exists() else {}
        solid=s['bond_frozen'];fractures=s['bond_broken']&solid[s['bond_edges']].all(1)
        status='running' if name in active else proof.get('status','stopped')
        if status=='complete':status='test interval complete'
        if proof.get('error','') and str(proof['error']).startswith('TimeoutError'):status='paused at compute limit'
        digest=hashlib.sha256((folder/'state.npz').read_bytes()).hexdigest()
        audit_path=folder/'acceptance.json'
        audit=json.loads(audit_path.read_text()) if audit_path.exists() else {}
        if audit.get('stateSha256')!=digest:audit={}
        runs.append(dict(name=name,label=label,status=status,time=meta['time'],particles=len(s['x']),
                         gridMm=min(meta['cell_size'])*1000,fracturedSolidEdges=int(fractures.sum()),
                         thermalResidual=max((r['thermalBalanceRelative'] for r in meta['rows']),default=0),
                         mechanicalResidual=max((r['mechanicalResidual'] for r in meta['rows']),default=0),
                         timeAccuracy='passes to saved time' if audit.get('temporalChecks') else 'not validated',
                         stateSha256=digest))
    checks={}
    for name in ['process','degradation','inlet','pipe-heat','bed-resume','linesearch','publication','initial-volume','backend','friction-backend','temporal','adaptive','creep-damping','preflight','trbdf2-coupled']:
        path=ROOT/'rebuild-38'/(name+'-check.json')
        if path.exists():checks[name]=json.loads(path.read_text())
    report=dict(updated=datetime.now(timezone.utc).isoformat(),finalVisualAccepted=False,beautyRenderPublished=False,
                runs=runs,checks=checks,remaining=['Sustained crust fracture and breakup','Whole-sequence temporal and spatial convergence','Geometry and motion at converged resolution','Smoke/heat coupling','Mitsuba material and final visual review'])
    cooling_path=ROOT/'rebuild-38/cooling-timescale.json'
    if cooling_path.exists():
        cooling=json.loads(cooling_path.read_text());fine=cooling['cases'][-1]
        report['thermalColumnEstimate']=dict(firstCoherentTopSeconds=fine['firstCoherentTopSeconds'],firstTopBelow1000KSeconds=fine['firstTopBelow1000KSeconds'],scope=cooling['scope'],timeRefinementK=cooling['maximumTopTemperatureChangeUnderTimeRefinementK'],spaceRefinementK=cooling['maximumTopTemperatureChangeUnderSpaceRefinementK'])
    DEST.mkdir(parents=True,exist_ok=True)
    (DEST/'progress-38.json').write_text(json.dumps(report,indent=2))
    shutil.copyfile(ROOT/'rebuild-38/initial-boundary-comparison.png',DEST/'boundary-38.png')
    if (ROOT/'rebuild-38/adaptive-flow-review.png').exists():shutil.copyfile(ROOT/'rebuild-38/adaptive-flow-review.png',DEST/'adaptive-flow-38.png')
    if cooling_path.exists():shutil.copyfile(cooling_path,DEST/'cooling-timescale-38.json')
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cybrdelic — lava rebuild progress</title><style>
*{box-sizing:border-box}body{margin:0;background:#000;color:#ded3c9;font:15px/1.6 system-ui}main{max-width:1440px;margin:auto;padding:26px 4% 64px}header{display:flex;justify-content:space-between;border-bottom:1px solid #32281f;padding-bottom:16px;font-size:11px;letter-spacing:.13em}a{color:#d8a478}h1{font-size:clamp(30px,5vw,50px);font-weight:450;letter-spacing:-.04em;line-height:1.12;margin:32px 0 14px}h2{font-size:20px;font-weight:500;margin-top:32px}p{max-width:920px;color:#b8aca1}.notice{border-left:2px solid #b57c51;padding:8px 18px;margin:24px 0}figure{margin:24px 0}img{display:block;width:100%;height:auto;background:#000}figcaption,footer,.muted{font-size:12px;color:#a39589}details{margin:24px 0;border-top:1px solid #32281f;padding-top:18px}summary{cursor:pointer}strong{font-weight:550;color:#ded3c9}.table{overflow:auto}table{width:100%;border-collapse:collapse;text-align:left;font-size:13px}td,th{padding:12px;border-bottom:1px solid #29231e;white-space:nowrap}th{font-weight:500;color:#a39589}.previous{max-width:640px}
</style><main><header><span>CYBRDELIC / LAVA</span><a href="../">Lava studies</a></header>
<h1>Fixing the simulation.</h1>
<p class="notice"><strong>No final lava render has passed review.</strong><br>The images below are CPU geometry diagnostics. They show a specific repair; they are not the finished material or video.</p>
<h2>A smoother starting surface, with the correct mass.</h2>
<p>The old shape started with visible steps because boundary cells were either full or empty. The revised initializer measures how much lava occupies each boundary cell. The comparison uses the same camera and scale.</p>
<figure><a href="boundary-38.png"><img src="boundary-38.png" width="1440" height="585" alt="Four fixed-camera diagnostic views: original and corrected boundary sampling at two grid resolutions"></a><figcaption>Geometry above; temperature below. Both revised starting volumes agree with an independent volume integral to within 0.011%. Residual surface bands still need review during motion.</figcaption></figure>
<h2>Verified repairs</h2>
<p>Corrected a stress/heat spike near fracture, the pipe’s collision and thermal boundaries, and a pressure step that failed at finer resolution. Rock now absorbs heat and warms up. Checkpoints retain the source schedule and rock state.</p>
<p>Final publication requires physical checks, actual open fractures, and a review of geometry, motion and resolution tied to the exact cache. Melting connections no longer count as solid fractures.</p>
<h2>Simulation evidence</h2><div class="table"><table><thead><tr><th>Test</th><th>Status</th><th>Simulated time</th><th>Grid</th><th>Time accuracy</th><th>Solid fracture edges</th></tr></thead><tbody id="runs"></tbody></table></div><p class="muted" id="stamp"></p>
<p>A fixed-step control missed the temperature accuracy limit. Automatic timestep refinement now passes both startup and the previously stalled cooling interval. The longer run passes its error checks through the saved time, but has not finished its requested interval. An experimental higher-order heat method failed the coupled test and is not used.</p>
<details><summary>Current CPU frames — rejected for final presentation</summary><figure><img src="adaptive-flow-38.png" width="1440" height="585" loading="lazy" alt="Four stages of the adaptive lava specimen, showing cohesive but visibly banded geometry without open cracks"><figcaption>The mass stays connected. Surface bands remain and there are no open cracks. This is a small physical specimen, not the sigil or a finished lava shot.</figcaption></figure></details>
<h2>The shot was being judged too early.</h2><p>A separate thermal column estimates roughly 11 seconds for the exposed top to form a coherent crust, and 39 seconds to fall below 1000 K. It includes conduction, latent heat, radiation and a finite rock bed; it omits flow, lateral cooling and the hot inlet. These estimates expose a timing problem, but are not a prediction of the finished 3D shot. <a href="cooling-timescale-38.json">Thermal comparison and refinement results</a>.</p>
<h2>Still unresolved</h2><p>Sustained breakup of a thick crust, full-sequence accuracy and resolution, the quality of the moving surface, smoke and heat coupling, and the final Mitsuba appearance. Passing a numerical test does not mean these are fixed.</p>
<details><summary>Previous render — rejected</summary><figure class="previous"><img src="basalt-material-37.png" loading="lazy" width="1440" height="900" alt="Previous rejected basalt material study"><figcaption>This used pre-existing fragments and a separate temperature treatment. It is retained for reference.</figcaption></figure><a href="material-37.html">Previous material study and limitations</a></details>
<footer><a href="progress-38.json">Measured progress and test records</a></footer></main>
<script>fetch('progress-38.json',{cache:'no-store'}).then(r=>r.json()).then(data=>{for(const r of data.runs){const tr=document.createElement('tr');for(const value of [r.label,r.status,r.time.toFixed(2)+' s',r.gridMm.toFixed(2)+' mm',r.timeAccuracy,r.fracturedSolidEdges]){const td=document.createElement('td');td.textContent=value;tr.append(td)}document.getElementById('runs').append(tr)}document.getElementById('stamp').textContent='Snapshot updated '+new Date(data.updated).toLocaleString()+'. Simulated time is a measurement, not a completion percentage.'}).catch(()=>{document.getElementById('stamp').textContent='Progress data could not be loaded.'})</script></html>'''
    (DEST/'index.html').write_text(html,encoding='utf-8')
    print(json.dumps(dict(page=str(DEST/'index.html'),runs=len(runs),checks=len(checks),finalVisualAccepted=False)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--active',nargs='*',default=[]);a=p.parse_args();build(a.active)
