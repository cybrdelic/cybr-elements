"""Publish CPU structural evidence at the existing lava repairs page."""
import hashlib,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from lava_mpm import ROOT
from lava_mpm_surface import extract,image_surface
from lava_mpm_render_gate import inspect_surface
from lava_mpm_validate import TESTS


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    project=Path(__file__).resolve().parents[3]
    out=project/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava/mpm/repairs'
    out.mkdir(parents=True,exist_ok=True)
    cold=ROOT/'upper-crust-23';loaded=ROOT/'upper-crust-load-23'
    proof=json.loads((loaded/'proof.json').read_text())
    assert proof['status']=='pass'
    assert proof['source']['sourceSha256']==sha(cold/'state.npz')
    cold_surface=extract(cold/'state.npz',method='material');cold_image=image_surface(cold_surface)
    surface=extract(loaded/'state.npz',method='material');loaded_image=image_surface(surface)
    # Same state, same camera, explicit legacy density diagnostic. This must
    # never overwrite the fracture-aware export or its source receipt.
    kernel_state=loaded/'kernel-comparison.npz';shutil.copy2(loaded/'state.npz',kernel_state)
    kernel_surface=extract(kernel_state,method='kernel');kernel_image=image_surface(kernel_surface,camera=np.load(surface))
    canvas=Image.new('RGB',(1440,495));draw=ImageDraw.Draw(canvas)
    for i,(path,title) in enumerate([(kernel_image,'Previous density surface: fractures blended together'),(loaded_image,'Material boundary: open faces retained')]):
        with Image.open(path) as im:canvas.paste(im.crop((0,480,720,885)),(i*720,40))
        draw.text((i*720+20,15),title,fill='#d2c7bc')
    draw.text((20,467),'Identical simulated state and camera. CPU geometry diagnostic; controlled tensile specimen, not final lava artwork.',fill='#9c928a')
    comparison=loaded/'same-state-comparison.png';canvas.save(comparison)
    gate=inspect_surface(surface)
    assert gate['status']=='blocked' and not gate['checks']['productionScene'],'A loaded test must never be promoted as a final lava shot'
    names=list(TESTS)+['inlet_source','solid_floor_contact','rectangular_grid','bonded_substrate',
        'crystal_network','local_fracture','fractured_inlet_boundary','phase_contact_transition',
        'continuous_phase_optics','material_surface','material_boundary_topology','upper_crust_fracture_export']
    tests={name:json.loads((ROOT/'validation'/f'{name}.json').read_text()) for name in names}
    assert all(q['status']=='pass' for q in tests.values())
    assets=[(comparison,'geometry-comparison.png'),(cold_image,'cooling-proof.png'),
        (loaded_image,'fracture-proof.png'),(ROOT/'surface-proof-22/surface-tests.png','surface-tests.png')]
    asset_receipts={}
    for source,name in assets:
        shutil.copy2(source,out/name)
        with Image.open(source) as picture:
            assert max(picture.size)<=1600
            asset_receipts[name]=dict(size=picture.size,bytes=source.stat().st_size,sha256=sha(source))
    timestep_path=ROOT/'validation/upper_crust_timestep.json'
    timestep=json.loads(timestep_path.read_text()) if timestep_path.exists() else {'status':'not yet evaluated'}
    result=dict(status='Structural mechanism demonstrated; final lava appearance unfinished',
        finalRenderAccepted=False,device='CPU only',passingChecks=len(tests),checks=tests,
        cooling=json.loads((cold/'progress.json').read_text()),fracture=proof,
        surface=json.loads(surface.with_suffix('.json').read_text()),renderPreflight=gate,timestep=timestep,
        sourceSha256=sha(loaded/'state.npz'),assets=asset_receipts,
        remaining=['The test uses explicit end grips; it does not prove spontaneous free-flow crust breakup.',
            'The material-cell surface still shows grid-scale facets. It is not the final basalt surface.',
            'Spatial/fracture convergence, capillarity, solid-solid friction, gas coupling and the final material look remain unproved.',
            'No new full-size animation or GPU render was launched.'])
    (out/'review.json').write_text(json.dumps(result,indent=2))
    # Keep the preceding page and its rendered comparison available.
    previous=out/'previous-review.html'
    if (out/'index.html').exists() and not previous.exists():shutil.copy2(out/'index.html',previous)
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cybrdelic — lava structure</title><style>
*{box-sizing:border-box}body{margin:0;background:#000;color:#e2d8cf;font:15px/1.6 system-ui}main{max-width:1240px;margin:auto;padding:26px 4% 64px}header{display:flex;justify-content:space-between;padding-bottom:16px;border-bottom:1px solid #32281f;font-size:11px;letter-spacing:.13em}a{color:#d8a478}h1{font-size:clamp(32px,5vw,58px);font-weight:450;letter-spacing:-.045em;line-height:1.1;margin:35px 0 18px}p{max-width:860px;color:#b8aca1}figure{margin:24px 0}img{display:block;width:100%;height:auto;background:#000}figcaption{font-size:12px;color:#a39589;margin:10px 0}.controls{display:flex;flex-wrap:wrap;gap:9px}button{font:inherit;font-size:13px;color:#c9b4a3;background:#000;border:1px solid #4b3628;padding:8px 14px;cursor:pointer}button[aria-pressed=true]{border-color:#d59a6c;color:#f7d6b9}.notice{border-left:2px solid #b57c51;padding:9px 17px;margin:23px 0 30px}details{border-top:1px solid #32281f;padding-top:18px;margin-top:30px}summary{cursor:pointer}li{margin:10px 0;color:#b8aca1;max-width:880px}.numbers{display:flex;gap:40px;flex-wrap:wrap;margin:26px 0}.numbers strong{font-size:28px;font-weight:450;display:block}.numbers span{font-size:12px;color:#a7978a}footer{margin-top:34px;font-size:12px}
</style><main><header><span>CYBRDELIC / LAVA</span><a href="../">Lava studies</a></header><h1>Crust that can actually break.</h1><p>The upper surface now cools into crust while the underside stays mostly molten. A controlled tensile test breaks that crust, and the exported geometry keeps the open fracture faces.</p><p class="notice"><strong>This is a CPU mechanism proof, not finished lava.</strong><br>The test uses explicit end grips. It does not establish natural flow breakup or the final basalt appearance. The production render gate rejects it as a final shot.</p><div class="controls"><button data-mode="compare" aria-pressed="true">Same-state comparison</button><button data-mode="cool" aria-pressed="false">Cooling</button><button data-mode="break" aria-pressed="false">Fracture under load</button><button data-mode="tests" aria-pressed="false">Mesh tests</button></div><figure><img id="hero" src="geometry-comparison.png" alt="Same simulated specimen with the previous density surface and the new fracture-aware material surface"><figcaption id="caption">The same particles, state and camera. The density surface blends the cracks together; the material boundary preserves them.</figcaption></figure><div class="numbers"><div><strong>__TOP__ K</strong><span>Upper surface after cooling</span></div><div><strong>__BONDS__</strong><span>Broken upper-crust bonds in load test</span></div><div><strong>0</strong><span>Broken basal bonds</span></div><div><strong>__VOLUME__%</strong><span>Exported volume difference</span></div></div><details><summary>Changes and evidence</summary><ul><li>Replaced the fracture-blind density export with locally connected material domains. Closed cracks add no line; open cracks retain their faces and remain attached at unresolved tips.</li><li>Removed the 95% tensile-damage cutoff that could prevent the later bond-release criterion from being reached.</li><li>New flow setups use 1 × 1 × 0.5 mm cells and a hot lower reservoir. Previous caches retain their original settings and are not relabeled.</li><li>Inlet births now have unique material coordinates. Fragment identity is an integer attribute, separate from solid fraction.</li><li>Resolved creases keep separate shading normals. No decorative crack pattern or pore displacement was added.</li><li>__CHECKS__ focused CPU checks pass. This count does not establish visual quality or convergence.</li></ul><p>The surface still has grid-scale facets. The next production case needs resolved natural breakup and a successful material review. These images should not be mistaken for that result.</p></details><footer><a href="review.json">Measured evidence</a> · <a href="method.md">Method and limits</a> · <a href="previous-review.html">Previous rejected render</a></footer></main><script>
const views={compare:['geometry-comparison.png','The same particles, state and camera. The density surface blends the cracks together; the material boundary preserves them.'],cool:['cooling-proof.png','18 seconds of fully coupled cooling from 1450 K. Temperature, phase, geometry and damage are diagnostic colors.'],break:['fracture-proof.png','18.08 seconds: thermally formed crust after 0.08 seconds under explicit end grips. No prescribed cracks or seeded damage.'],tests:['surface-tests.png','Independent geometric test coupons: intact, closed partial crack, open partial crack. These test cuts and displacements are prescribed, not simulated lava.']};document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{const v=views[button.dataset.mode];document.getElementById('hero').src=v[0];document.getElementById('caption').textContent=v[1];document.querySelectorAll('[data-mode]').forEach(q=>q.setAttribute('aria-pressed',String(q===button)));}));
</script></html>'''
    values=dict(TOP=f"{result['cooling']['metrics']['topMeanTemperatureK']:.0f}",BONDS=str(proof['metrics']['upperBrokenBonds']),VOLUME=f"{result['surface']['relativeVolumeDifference']*100:.2f}",CHECKS=str(len(tests)))
    for key,value in values.items():page=page.replace('__'+key+'__',value)
    page=page.replace('Crust that can actually break.','Crust and fracture diagnostics.')
    page=page.replace('The production render gate rejects it as a final shot.','The finer-timestep test still changes the motion and loading work substantially. Production rendering remains blocked.')
    page=page.replace('at unresolved tips','at connected tips')
    (out/'index.html').write_text(page,encoding='utf-8');shutil.copy2(ROOT/'README.md',out/'method.md')
    print(json.dumps(dict(page=str(out/'index.html'),status=result['status'],passingChecks=len(tests),assets=len(assets),renderPreflight=gate['status'])))


if __name__=='__main__':main()
