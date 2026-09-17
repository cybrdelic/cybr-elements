"""Publish this iteration's actual evidence without promoting a failed image."""
import json,shutil,hashlib,html
from pathlib import Path
import numpy as np
from lava_mpm import ROOT
from lava_mpm_surface import extract,image_surface


def main():
    project=Path(__file__).resolve().parents[3]
    out=project/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava/mpm'
    archive=out/'before-crust-update'
    if not archive.exists():
        archive.mkdir(parents=True)
        for name in ('index.html','material-fields.png','history.png','method.md','evidence.json'):
            if (out/name).exists():shutil.copy2(out/name,archive/name)
    runs={}
    for name,key in [('crust-local-10','coarse'),('crust-fine-11','fine')]:
        folder=ROOT/name;meta=json.loads((folder/'state.json').read_text());s=np.load(folder/'state.npz')
        surface=extract(folder/'state.npz');picture=image_surface(surface);shutil.copy2(picture,out/(key+'-fields.png'))
        runs[key]=dict(name=name,time=meta['time'],dx=meta['dx'],particles=len(s['x']),latest=meta['rows'][-1],stateSha256=hashlib.sha256((folder/'state.npz').read_bytes()).hexdigest())
    tests={p.stem:json.loads(p.read_text()) for p in sorted((ROOT/'validation').glob('*.json'))}
    passed=sum(t.get('status')=='pass' for t in tests.values());failed=sum(t.get('status')=='fail' for t in tests.values())
    difference=tests['material_grid_refinement']['relativeRmsSpeedDifference']*100
    rejected=dict(method='Corotated material-domain reconstruction',status='rejected',reason='Boxy terraces and grid-shaped holes; reconstructed volume differs by 7.54%. No final render used this mesh.')
    receipt=ROOT/'crust-local-10'/'state-domains.json'
    if receipt.exists():
        detail=json.loads(receipt.read_text());detail.update(numericalGate=False,visualStatus='rejected: particle-grid terraces and holes; not acceptable basalt');receipt.write_text(json.dumps(detail,indent=2))
    evidence=dict(status='not visually accepted; full lava simulation unfinished',device='CPU',passedChecks=passed,failedChecks=failed,runs=runs,tests=tests,rejectedReconstruction=rejected,
                  kept=['Crystal-packing network preserves solid shear stress','Conservative implicit viscous drag between melt and crust','Local fracture enrichment and matching pressure fields','Symmetric contact conditioning and relative support threshold'],
                  remaining=['Grid convergence: current early-flow RMS difference %.2f%% versus the unchanged 15%% gate'%difference,'Heavy, visibly separated basalt crust is not yet resolved','No sustained incoming lava in this finite cooling-sample scene','No complete coupled long lava/gas/bed run','Interfragment friction, degassing/condensation, full free-energy audit and calibrated material parameters remain unfinished'],
                  rendering='CPU diagnostic images only. No GPU or new Mitsuba/video batch.')
    (out/'evidence.json').write_text(json.dumps(evidence,indent=2));shutil.copy2(ROOT/'README.md',out/'method.md')
    def e(x):return html.escape(str(x))
    table=''.join(f'<tr><td>{e(k.replace("_"," "))}</td><td class="{e(v["status"])}">{e(v["status"])}</td></tr>' for k,v in tests.items())
    figures=''
    for key,label in [('coarse','Fracture mechanics study'),('fine','Finer early-cooling study')]:
        r=runs[key]
        figures+=f'<section><h2>{label}</h2><p class="meta">{r["particles"]:,} material points · {r["dx"]*1000:g} mm grid · {r["time"]:.2f} physical seconds</p><figure><img src="{key}-fields.png" alt="Actual CPU temperature, phase, surface geometry and damage fields"><figcaption>False-color diagnostics from the saved simulation. The surface is still too smooth and coarse for the requested fractured basalt. These two studies show different physical times and are not a matched-frame refinement comparison.</figcaption></figure></section>'
    document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cybrdelic — lava crust work</title><style>
*{box-sizing:border-box}body{margin:0;background:#000;color:#d3cdc5;font:15px/1.65 system-ui}main{max-width:1200px;margin:auto;padding:30px 5% 64px}header{display:flex;gap:24px;justify-content:space-between;border-bottom:1px solid #302922;padding-bottom:18px;font-size:12px;letter-spacing:.12em}a{color:#dcb394;text-underline-offset:4px}h1{font-size:clamp(34px,5vw,60px);font-weight:450;line-height:1.08;letter-spacing:-.045em;margin:42px 0 18px}h2{font-size:24px;font-weight:450;margin:38px 0 6px}.lead{max-width:850px;color:#a9a198}.status{border-left:3px solid #c7794a;padding:14px 20px;margin:28px 0;background:#110c08}.status strong{color:#edac7c}figure{margin:0}img{display:block;width:100%;height:auto;background:#000}figcaption,.meta,footer{font-size:12px;color:#a3988d}figcaption{padding:9px 0;max-width:940px}li{margin:9px 0}table{border-collapse:collapse;width:100%;font-size:13px}td{border-bottom:1px solid #24211e;padding:8px 12px}.pass{color:#98b5a0}.fail{color:#eaaa85}details{margin:35px 0}summary{cursor:pointer}footer{margin-top:40px}
</style><main><header><span>CYBRDELIC / LAVA</span><a href="../">Material references</a></header><h1>Crust mechanics update.</h1><p class="lead">The solver now retains solid crust stress, transfers viscous drag from the melt, and separates grid supports across a partial crack. The resulting lava geometry is still below the requested visual quality.</p><div class="status"><strong>Not accepted for final rendering.</strong><br>'''+str(passed)+''' component checks pass. The current grid comparison still fails: '''+f'{difference:.2f}%'+''' RMS speed difference against a 15% gate. The particle-domain surface trial was rejected for visible grid artifacts.</div><h2>Changes kept</h2><ul><li>Solid crust retains shear stress instead of relaxing with the melt’s viscosity.</li><li>Melt and crust exchange equal and opposite viscous forces; dissipated work returns to heat.</li><li>A crack can separate locally while the crust remains connected beyond its tip.</li><li>Contact uses a conditioned implicit solve and a relative support criterion.</li></ul>'''+figures+'''<h2>What still needs to improve</h2><ul>'''+''.join('<li>'+e(q)+'</li>' for q in evidence['remaining'])+'''</ul><p class="lead">More render samples would not repair the missing flow source or unresolved fracture geometry. No GPU or final render batch was used for this iteration.</p><details><summary>Numerical checks and evidence</summary><table><tbody>'''+table+'''</tbody></table></details><footer><a href="evidence.json">Evidence record</a> · <a href="method.md">Method and limits</a> · <a href="before-crust-update/">Earlier evidence</a></footer></main></html>'''
    (out/'index.html').write_text(document,encoding='utf-8')
    print(json.dumps(dict(page=str(out/'index.html'),images=['coarse-fields.png','fine-fields.png'],checksPassed=passed,checksFailed=failed,status=evidence['status'])))

if __name__=='__main__':main()
