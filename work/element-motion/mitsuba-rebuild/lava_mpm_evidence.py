"""Publish honest CPU evidence, with failed gates visible. No beauty renders."""
from pathlib import Path
import json,shutil,hashlib,html
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from lava_mpm import ROOT
from lava_mpm_surface import extract,image_surface

def main():
    project=Path(__file__).resolve().parents[3]
    out=project/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava/mpm'
    out.mkdir(parents=True,exist_ok=True)
    run=ROOT/'coupled-implicit-07';meta=json.loads((run/'state.json').read_text())
    surface=extract(run/'state.npz');diagnostic=image_surface(surface);shutil.copy2(diagnostic,out/'material-fields.png')
    rows=meta['rows'];t=np.array([r['time'] for r in rows]);phase=np.array([r['meanSolidFraction'] for r in rows]);temp=np.array([r['temperatureRange'] for r in rows])
    plt.rcParams.update({'figure.facecolor':'black','axes.facecolor':'black','savefig.facecolor':'black','text.color':'#d6d0c9','axes.labelcolor':'#bdb5ac','xtick.color':'#8e8880','ytick.color':'#8e8880','axes.edgecolor':'#39342f','font.size':10})
    fig,ax=plt.subplots(2,2,figsize=(14.4,8.2),dpi=100,constrained_layout=True)
    ax[0,0].fill_between(t,temp[:,0],temp[:,1],color='#a14825',alpha=.4);ax[0,0].plot(t,temp[:,1],color='#ed9056',label='hottest particle');ax[0,0].plot(t,temp[:,0],color='#9c684e',label='coldest particle');ax[0,0].set_ylabel('Temperature / K');ax[0,0].legend(frameon=False,labelcolor='#bbb')
    ax[0,1].plot(t,phase*100,color='#87bfc6');ax[0,1].set_ylabel('Mean solid fraction / %');ax[0,1].set_ylim(0,100)
    ax[1,0].plot(t,[r['maximumSpeed'] for r in rows],color='#d2b77c');ax[1,0].set_ylabel('Maximum material speed / m/s')
    ax[1,1].plot(t,[r.get('materialVelocityFields',1) for r in rows],color='#aa9ad1',label='independent fields');ax[1,1].plot(t,[r.get('brokenConnectivityEdges',0) for r in rows],color='#e7846c',label='broken edges');ax[1,1].set_ylabel('Count');ax[1,1].legend(frameon=False,labelcolor='#bbb')
    for a in ax.ravel():a.set_xlabel('Physical time / seconds');a.grid(alpha=.12);a.spines[['top','right']].set_visible(False)
    fig.suptitle('Material-only regression cache — fixed cold substrate\nSeparate from the gas and finite-bed tests; not a completed production shot',fontsize=13,color='#ddd')
    fig.savefig(out/'history.png');plt.close(fig)
    tests={p.stem:json.loads(p.read_text()) for p in sorted((ROOT/'validation').glob('*.json'))}
    passed=sum(v.get('status')=='pass' for v in tests.values());failed=sum(v.get('status')=='fail' for v in tests.values())
    refinement=tests['material_grid_refinement'];difference=refinement['relativeRmsSpeedDifference']*100
    limits=[
        f'The 10 mm → 5 mm material-grid comparison changed RMS speed by {difference:.2f}%; the 15% gate failed.',
        'Long-time fracture convergence, a Coulomb interfragment friction solve, and a complete free-energy audit remain unfinished.',
        'The gas has heat, pressure and energy-limited fracture dust. Volcanic degassing, bubbles and steam condensation are not implemented.',
        'The finite rock bed passed a heat-exchange test. It was not used in the material-only cache shown above.',
        'The current sample is approximately 10 cm across. Nominal material properties and dust parameters have not been experimentally calibrated.',
        'The old separately authored magma/lava/basalt/obsidian images are not results from this solver.'
    ]
    evidence=dict(status='incomplete; full simulation not accepted',device='CPU',passedChecks=passed,failedChecks=failed,tests=tests,
                  materialCheckpoint=dict(physicalSeconds=meta['time'],particles=len(np.load(run/'state.npz')['x']),sourceSha256=hashlib.sha256((run/'state.npz').read_bytes()).hexdigest()),limits=limits,
                  renders='CPU diagnostics only; no final Mitsuba render or movie batch was started')
    (out/'evidence.json').write_text(json.dumps(evidence,indent=2));shutil.copy2(ROOT/'README.md',out/'method.md')
    table=''.join('<tr><td>'+html.escape(k.replace('_',' '))+'</td><td class="'+v['status']+'">'+html.escape(v['status'])+'</td></tr>' for k,v in tests.items())
    document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cybrdelic — lava simulation evidence</title><style>
*{box-sizing:border-box}body{background:#000;color:#d8d1c8;font:15px/1.6 system-ui;margin:0}main{max-width:1200px;margin:auto;padding:28px 5% 70px}header{display:flex;justify-content:space-between;border-bottom:1px solid #302a25;padding-bottom:18px;font-size:12px;letter-spacing:.12em}a{color:#d5b291;text-underline-offset:5px}h1{font-size:clamp(30px,6vw,64px);font-weight:450;letter-spacing:-.055em;line-height:1.05;margin-bottom:18px}.lead{max-width:800px;color:#a9a198}.status{border-left:3px solid #de8656;padding:12px 18px;margin:28px 0;background:#100b08}.status strong{color:#ed9c76}h2{font-size:23px;font-weight:450;margin-top:42px}.visual{margin:20px 0}img{display:block;width:100%;height:auto;background:#000}figcaption{font-size:12px;color:#9c9389;margin:10px 0 26px}table{border-collapse:collapse;width:100%;font-size:13px}td{border-bottom:1px solid #24211e;padding:9px 12px}.pass{color:#90b6a0}.fail{color:#eea17c}li{margin:12px 0;color:#afa79e}footer{margin-top:40px;font-size:12px;color:#948a80}
</style><main><header><span>CYBRDELIC / LAVA</span><a href="../">Material references</a></header><h1>Simulation evidence.</h1><p class="lead">A new three-dimensional CPU MPM implementation. The full lava simulation is not finished or validated yet.</p><div class="status"><strong>'''+str(passed)+''' checks pass · '''+str(failed)+''' accuracy gate fails</strong><br>Material-grid refinement changes flow speed by '''+f'{difference:.2f}%'+'''. Final rendering is on hold.</div><h2>Actual material state</h2><figure class="visual"><img src="material-fields.png" alt="CPU diagnostic views of temperature, solid fraction, geometry and damage from the material checkpoint"><figcaption>One evolving material cache at '''+f'{meta["time"]:.2f}'+''' physical seconds. False-color diagnostics; no sculpted crack lines or authored stage meshes.</figcaption></figure><figure class="visual"><img src="history.png" alt="Temperature, solid fraction, speed and material-field count over physical time"><figcaption>The source hashes and individual test results are in the <a href="evidence.json">evidence record</a>.</figcaption></figure><h2>What still prevents calling this complete</h2><ul>'''+''.join('<li>'+html.escape(s)+'</li>' for s in limits)+'''</ul><h2>CPU checks</h2><table><tbody>'''+table+'''</tbody></table><footer><a href="method.md">Method and limitations</a> · <a href="evidence.json">Numerical evidence</a><p>CPU only. These checks do not establish photorealism or production readiness.</p></footer></main></html>'''
    (out/'index.html').write_text(document,encoding='utf-8')
    print(json.dumps(dict(path=str(out/'index.html'),passed=passed,failed=failed,physicalSeconds=meta['time'],images=['material-fields.png','history.png'])))
if __name__=='__main__':
    from lava_mpm_repair_review import main as current_review
    current_review()
