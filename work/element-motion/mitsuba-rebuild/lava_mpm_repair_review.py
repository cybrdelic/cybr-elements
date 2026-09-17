"""Publish a rejected CPU repair proof without promoting it as finished lava."""
import json,hashlib,shutil,html
from pathlib import Path
from PIL import Image
import numpy as np
from lava_mpm import ROOT
from lava_mpm_validate import TESTS

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def legacy_main():
    project=Path(__file__).resolve().parents[3]
    public=project/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava/mpm'
    out=public/'repairs';out.mkdir(parents=True,exist_ok=True)
    flow=ROOT/'continuous-21';cool=ROOT/'continuous-21-cooling'
    optical=json.loads((flow/'optical-proof/state.json').read_text())
    surface=json.loads((flow/'state-surface.json').read_text())
    assert optical['sourceSha256']==sha(flow/'state-surface.npz')
    assert surface['sourceSha256']==sha(flow/'state.npz')
    cool_surface=json.loads((cool/'state-surface.json').read_text())
    assert cool_surface['sourceSha256']==sha(cool/'state.npz')
    selected=list(TESTS)+['inlet_source','solid_floor_contact','rectangular_grid','bonded_substrate','crystal_network','local_fracture','fractured_inlet_boundary','phase_contact_transition','continuous_phase_optics']
    tests={key:json.loads((ROOT/'validation'/f'{key}.json').read_text()) for key in selected}
    assert all(item['status']=='pass' for item in tests.values())
    failures={key:json.loads((ROOT/'validation'/f'{key}.json').read_text()) for key in ['material_grid_refinement','continuous_timestep']}
    fixes=['Removed the specified initial slabs and pore cuts from the replacement case.',
           'Added finer vertical MPM cells with axis-correct transfer, heat conduction and boundary geometry.',
           'Aligned crystal-network, connectivity and tensile-failure activation.',
           'Preserved Newtonian melt viscosity after fracture and verified remelted damaged material against fresh liquid.',
           'Corrected fractured inlet/ground reflection and tested the captured failure.',
           'Kept coupled contact constraints that become active during the solve.',
           'Removed stretched-kernel surface terraces and verified continuous solid-fraction import into Mitsuba.']
    rejection=['The rendered body still reads as a smooth hot lump, not heavy fractured basalt.',
               'There is no convincing visible broken crust or open fracture structure.',
               'The inlet cavities and patchy highlights are not a successful lava surface.',
               'Exposure changes do not solve these geometry and material problems.']
    review=dict(status='rejected',target='Heavy fractured basalt with glowing cracks on pitch black',observations=rejection,
                finalRenderAccepted=False,fixes=fixes,cpuChecks=tests,passingRelevantChecks=len(tests),
                unresolvedSpatialGate=failures['material_grid_refinement'],rejectedLargerTimestepTrial=failures['continuous_timestep'],
                selectedStepping='Conservative original limits retained; the failed larger-step trial was not adopted.',
                flow=json.loads((flow/'progress.json').read_text()),cooling=json.loads((cool/'progress.json').read_text()),
                surface=surface,coolingSurface=cool_surface,renderer=optical,reviewExposure=2.,
                sources={name:sha(Path(__file__).parent/name) for name in ['lava_mpm.py','lava_mpm_fracture.py','lava_mpm_inlet.py','lava_mpm_continuous.py','lava_mpm_cooling_pulse.py','lava_mpm_surface.py','lava_mpm_render.py','lava_emission_io.py']},
                limits=['The 4 cm specimen and nominal rheology do not establish production lava behavior.',
                        'Surface reconstruction does not resolve subgrid cracks or a detailed basalt shell.',
                        'Liquid surface tension is not implemented; fracture energy is not a substitute for capillarity.',
                        'Solid/solid friction, fracture convergence and a complete mechanical/thermal energy audit remain unresolved.',
                        'The bed is an ideal bonded hot reservoir. Gas, degassing and dust are not active in these cases.'])
    for folder in (flow,cool):(folder/'visual-review.json').write_text(json.dumps(dict(status='rejected',target=review['target'],observations=rejection),indent=2))
    assets=[(flow/'optical-proof/state-exposure-2.png','current-check.png'),(flow/'optical-proof/exposure-review.png','exposure-check.png'),
            (flow/'state-surface-diagnostic.png','flow-fields.png'),(cool/'state-surface-diagnostic.png','cooling-fields.png'),
            (ROOT/'fractured-feed-18/optical-proof/state.png','previous-slab.png')]
    review['assets']={}
    for source,name in assets:
        shutil.copy2(source,out/name)
        with Image.open(source) as picture:
            width,height=picture.size;assert max(width,height)<=1600
            review['assets'][name]=dict(width=width,height=height,sha256=sha(source),bytes=source.stat().st_size)
    picture=np.array(Image.open(out/'current-check.png').convert('RGB'))
    assert not picture[0].any() and not picture[-1].any() and not picture[:,0].any() and not picture[:,-1].any()
    review['blackBorderVerified']=True
    (out/'review.json').write_text(json.dumps(review,indent=2));shutil.copy2(ROOT/'README.md',out/'method.md')
    changes=''.join('<li>'+html.escape(line)+'</li>' for line in fixes)
    observations=''.join('<li>'+html.escape(line)+'</li>' for line in rejection)
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cybrdelic — lava repair check</title><style>
*{box-sizing:border-box}body{margin:0;background:#000;color:#d8d0c8;font:15px/1.6 system-ui}main{max-width:1160px;margin:auto;padding:28px 5% 60px}header{display:flex;justify-content:space-between;font-size:11px;letter-spacing:.13em;border-bottom:1px solid #302821;padding-bottom:16px}a{color:#d5a883}h1{font-size:clamp(30px,5vw,54px);line-height:1.08;font-weight:450;letter-spacing:-.04em}p,li{max-width:860px;color:#aea398}figure{margin:24px 0}img{display:block;width:100%;height:auto;background:#000}figcaption{color:#958a80;font-size:12px;margin-top:10px}.status{border-left:2px solid #b96d42;padding:10px 18px}.controls{display:flex;flex-wrap:wrap;gap:10px}button{font:inherit;font-size:13px;background:#000;color:#c6b6a9;border:1px solid #4c382b;padding:9px 14px;cursor:pointer}button[aria-pressed=true]{border-color:#d99462;color:#f2ccaa}details{margin-top:30px;border-top:1px solid #302821;padding-top:16px}summary{cursor:pointer}li{margin:9px 0}h2{font-size:23px;font-weight:450;margin-top:36px}footer{font-size:12px;margin-top:36px}
</style><main><header><span>CYBRDELIC / LAVA</span><a href="../">Previous slab study</a></header><h1>Lava repair check.</h1><p class="status"><strong>Still below the visual target.</strong><br>The solver repairs pass their component checks. The new image is still too smooth and artificial to call the lava fixed.</p><div class="controls"><button data-mode="current" aria-pressed="true">Current CPU check</button><button data-mode="previous" aria-pressed="false">Previous slab image</button><button data-mode="cooling" aria-pressed="false">Cooling diagnostic</button></div><figure><img id="hero" src="current-check.png" alt="Rejected CPU proof of a smooth molten body"><figcaption id="caption">2.333 physical seconds · 640 × 400 · 6 samples · Mitsuba CPU · rejected visual proof</figcaption></figure><h2>What the image still fails</h2><ul>'''+observations+'''</ul><details><summary>Implemented repairs and CPU evidence</summary><ul>'''+changes+'''</ul><p>25 relevant component checks pass. The earlier spatial refinement gate is still unresolved. A larger-timestep trial failed and was rejected. These results do not establish production realism.</p><p>The inlet stopped at 2.333 seconds; the same material then cooled in the full mechanical and thermal solve to 4.994 seconds. No hand-painted cracks or extra cooling sink were added. The cooling diagnostic also fails the visual target.</p><p>The original 0.6 exposure was too dark. This image uses exposure 2 from the same saved radiance; no extra rendering was performed for exposure review.</p><img src="exposure-check.png" alt="Three exposures of the same rejected material proof"></details><footer><a href="review.json">Repair evidence</a> · <a href="method.md">Method and remaining limits</a></footer></main><script>
const views={current:['current-check.png','2.333 physical seconds · 640 × 400 · 6 samples · Mitsuba CPU · rejected visual proof'],previous:['previous-slab.png','Previous specified-clast study. Rejected: pre-cut slabs, drilled-looking pores and uniform orange melt. This uses a different initial condition.'],cooling:['cooling-fields.png','4.994 physical seconds · actual temperature, phase, geometry and damage · false-color CPU diagnostic, not a beauty render']};document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{const view=views[button.dataset.mode];document.getElementById('hero').src=view[0];document.getElementById('caption').textContent=view[1];document.querySelectorAll('[data-mode]').forEach(q=>q.setAttribute('aria-pressed',String(q===button)));}));
</script></html>'''
    (out/'index.html').write_text(page,encoding='utf-8')
    # Preserve the earlier page, then make its rejection visible in place.
    index=public/'index.html';archive=public/'rejected-fractured-feed-18'
    if not archive.exists():
        archive.mkdir()
        for source in public.iterdir():
            if source.is_file():shutil.copy2(source,archive/source.name)
    old=index.read_text(encoding='utf-8')
    if 'id="lava-repair-status"' not in old:
        old=old.replace('<main>','<main><p id="lava-repair-status" class="note"><strong>This slab image is rejected.</strong> The replacement also remains below the target. <a href="repairs/">View the current CPU repair check.</a></p>',1)
        old=old.replace('<h1>Crust, with room to move.</h1>','<h1>Rejected slab study.</h1>')
        index.write_text(old,encoding='utf-8')
    print(json.dumps(dict(page=str(out/'index.html'),status='rejected visual proof; numerical repairs retained',relevantChecks=len(tests),assets=len(assets),device='CPU')))

def main():
    if (ROOT/'upper-crust-load-23/proof.json').exists():
        from lava_mpm_structural_review import main as structural_review
        return structural_review()
    return legacy_main()


if __name__=='__main__':main()
