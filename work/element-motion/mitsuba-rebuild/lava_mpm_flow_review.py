"""Publish actual CPU material proofs with their initial-condition boundary."""
import argparse,json,shutil,hashlib,html
from pathlib import Path
import numpy as np
from lava_mpm import ROOT


def main(name):
    project=Path(__file__).resolve().parents[3];out=project/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava/mpm';out.mkdir(parents=True,exist_ok=True)
    archive=out/'before-inlet-update'
    if not archive.exists():
        archive.mkdir()
        for file in out.iterdir():
            if file.is_file():shutil.copy2(file,archive/file.name)
    folder=ROOT/name;setup=json.loads((folder/'inlet.json').read_text());meta=json.loads((folder/'state.json').read_text());surface=json.loads((folder/'state-surface.json').read_text());proof=json.loads((folder/'optical-proof/state.json').read_text())
    assert hashlib.sha256((folder/'state-surface.npz').read_bytes()).hexdigest()==proof['sourceSha256']
    assert hashlib.sha256((folder/'state.npz').read_bytes()).hexdigest()==surface['sourceSha256']
    for source,destination in [(folder/'optical-proof/state.png','lava-current.png'),(folder/'state-surface-diagnostic.png','lava-fields.png'),(ROOT/'inlet-conduit-13/optical-proof/state.png','lava-before.png')]:shutil.copy2(source,out/destination)
    snapshots=[]
    for path in sorted(folder.glob('frame-*-surface-diagnostic.png')):
        destination=path.name;shutil.copy2(path,out/destination)
        source=np.load(path.with_name(path.name.replace('-surface-diagnostic.png','.npz')))
        snapshots.append(dict(time=float(source['time']),image=destination))
    tests={p.stem:json.loads(p.read_text()) for p in sorted((ROOT/'validation').glob('*.json'))}
    tests={k:v for k,v in tests.items() if v.get('status') in ('pass','fail')}
    passed=sum(v.get('status')=='pass' for v in tests.values());failed=sum(v.get('status')=='fail' for v in tests.values())
    report=dict(status='reviewable CPU study; not a completed production lava simulation',run=name,device='CPU',renderer=proof,
                initialCondition=setup,physicalTime=meta['time'],latest=meta['rows'][-1],surface=surface,tests=tests,passedChecks=passed,failedChecks=failed,
                kept=['Mass/enthalpy-accounted molten inlet with nonzero boundary work','Free solid floor contact replaces the remote no-slip pinning of hovering crust','Separate embedded basalt boundaries preserve actual gaps','Declared irregular, porous initial crust volume; no animated fragment paths','Mitsuba CPU path tracing on an exactly black backdrop'],
                limits=['Initial fractures and pores are specified; their formation is not simulated','This is a short coarse study, not the complete lava/gas/bed simulation','The last early-flow grid refinement result still fails its 15% gate','Embedded clast boundaries use fitted affine motion; reported error does not establish continuum convergence','Melt surface detail, fracture-face detail and solid contact/friction still need improvement','Pore bump is an optical approximation; melt/solid kernels may overlap at unresolved interfaces'],
                snapshots=snapshots)
    (out/'evidence.json').write_text(json.dumps(report,indent=2));shutil.copy2(ROOT/'README.md',out/'method.md')
    data=json.dumps(snapshots).replace('<','\\u003c');safe=html.escape
    description=f'{meta["time"]:.3f} s simulated · {meta["rows"][-1]["particles"]:,} material points · Mitsuba CPU · {proof["width"]} × {proof["height"]}'
    document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cybrdelic — lava flow study</title><style>
*{box-sizing:border-box}body{margin:0;background:#000;color:#d4cec7;font:15px/1.65 system-ui}main{max-width:1220px;margin:auto;padding:26px 5% 64px}header{display:flex;justify-content:space-between;font-size:11px;letter-spacing:.17em;border-bottom:1px solid #28201b;padding-bottom:16px}a{color:#cba585;text-underline-offset:4px}h1{font-size:clamp(32px,5vw,58px);font-weight:450;letter-spacing:-.04em;line-height:1.08;margin:38px 0 16px}p{max-width:880px;color:#a39a91}figure{margin:0}img{width:100%;display:block;background:#000}figcaption,.meta{font-size:12px;color:#92887e}figcaption{padding:10px 0 18px}.note{border-left:2px solid #b9723f;padding:8px 20px}.controls{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}button{font:inherit;font-size:13px;padding:9px 15px;border:1px solid #463328;background:#090706;color:#cdbbaa;border-radius:3px;cursor:pointer}button[aria-pressed=true]{color:#f3d3b4;border-color:#bf7640}h2{font-size:22px;font-weight:450;margin:34px 0 12px}details{border-top:1px solid #27201b;padding-top:18px;margin-top:28px}summary{cursor:pointer}li{color:#a89e94;margin:8px 0}table{border-collapse:collapse;width:100%;font-size:12px}td{padding:7px;border-bottom:1px solid #25201c}.pass{color:#95b09e}.fail{color:#e5a27b}input[type=range]{width:min(480px,70%);accent-color:#bd7544}footer{margin-top:36px;font-size:12px}
</style><main><header><span>CYBRDELIC / LAVA</span><a href="../">Earlier material work</a></header><h1>Crust, with room to move.</h1><p>The floor no longer pins hovering basalt. Incoming melt now loads separate solid pieces, with heat and mass tracked through the simulation.</p><div class="controls"><button id="current" aria-pressed="true">Current CPU render</button><button id="before" aria-pressed="false">Earlier inlet test</button></div><figure><img id="hero" src="lava-current.png" alt="CPU Mitsuba rendering of thick basalt pieces over molten lava on black"><figcaption id="caption">'''+safe(description)+'''</figcaption></figure><p class="note">This study starts with fractured, porous basalt already present. Its movement is simulated; the initial cracks and pores are specified geometry. It is not the complete magma-to-basalt simulation or a finished production shot.</p><h2>Saved simulation states</h2><p>Scrub the actual cached states. These are diagnostic images, with temperature, phase, geometry and damage shown separately.</p><div class="controls"><input id="time" aria-label="Saved simulation state" type="range" min="0" max="'''+str(max(0,len(snapshots)-1))+'''" value="'''+str(max(0,len(snapshots)-1))+'''"><span id="timestamp" class="meta"></span></div><img id="fields" src="lava-fields.png" alt="Four diagnostic panels of actual simulation state"><details><summary>Method, checks, and remaining limitations</summary><p>'''+str(passed)+''' component checks pass; '''+str(failed)+''' check remains failed. Passing component tests do not establish production realism or grid convergence.</p><ul>'''+''.join('<li>'+safe(q)+'</li>' for q in report['limits'])+'''</ul><table>'''+''.join('<tr><td>'+safe(k.replace('_',' '))+'</td><td class="'+safe(v['status'])+'">'+safe(v['status'])+'</td></tr>' for k,v in tests.items())+'''</table></details><footer><a href="evidence.json">Evidence and render settings</a> · <a href="method.md">Solver method</a> · <a href="before-inlet-update/">Previous evidence</a></footer></main><script>
const frames='''+data+''';const state=document.getElementById('time'),fields=document.getElementById('fields'),stamp=document.getElementById('timestamp');function update(){if(!frames.length)return;const f=frames[Number(state.value)];fields.src=f.image;stamp.textContent=f.time.toFixed(3)+' s';}state.addEventListener('input',update);update();const hero=document.getElementById('hero'),caption=document.getElementById('caption');for(const id of ['current','before'])document.getElementById(id).addEventListener('click',()=>{hero.src=id==='current'?'lava-current.png':'lava-before.png';caption.textContent=id==='current'?'''+json.dumps(description)+''': 'Earlier inlet experiment. Rejected: smooth red lump and cropped framing. This is a different initial condition, not a matched-state comparison.';for(const q of ['current','before'])document.getElementById(q).setAttribute('aria-pressed',String(q===id));});</script></html>'''
    (out/'index.html').write_text(document,encoding='utf-8')
    print(json.dumps(dict(page=str(out/'index.html'),snapshots=len(snapshots),passed=passed,failed=failed,status=report['status'])))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='fractured-feed-18');a=p.parse_args();main(a.name)
