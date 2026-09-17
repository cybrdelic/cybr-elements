"""Validate and publish the inspected CPU lava stills on the existing page."""
from pathlib import Path
import json,hashlib,shutil
import numpy as np
from PIL import Image

R=Path(__file__).resolve().parent;L=R/'lava-focus'
P=R.parents[2]/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(stem):
    path=L/'renders'/stem;receipt=json.loads(path.with_suffix('.json').read_text());im=np.array(Image.open(path.with_suffix('.png')));raw=np.load(str(path)+'-raw-aov.npz')['color']
    assert receipt['device']=='CPU' and receipt['variant']=='scalar_rgb' and receipt['threads']==2
    assert digest(path.with_suffix('.png'))==receipt['imageSha256']
    assert digest(Path(receipt['source']))==receipt['meshSha256']
    assert np.isfinite(raw).all() and raw.max()>0
    background=np.max(abs(raw),axis=-1)==0
    assert background.mean()>.05 and not im[background].any()
    assert np.all(im[:8]==0) and np.all(im[-8:]==0)
    receipt['blackPixelFraction']=float(background.mean())
    return path,receipt

def main():
    hero,hr=verify('lava-continuous-hero-0059-1280-8spp')
    detail,dr=verify('lava-continuous-detail-0059-1024-8spp')
    assert hr['meshSha256']==dr['meshSha256'] and hr['lightGain']==dr['lightGain']
    # Correct descriptive fields in the hero receipt made before the
    # renderer's metadata naming fix. Numerical/render data is unchanged.
    for field in ['geometryModel','backLight','geometryLimits']:hr[field]=dr[field]
    hero.with_suffix('.json').write_text(json.dumps(hr,indent=2))
    qa=json.loads((L/'lobes/qa.json').read_text())
    assert qa['openEdges']==0 and qa['nonManifoldEdges']==0 and qa['roundoffOnlyDegeneracies'] and qa['collapsedTriangleMaxEdgeM']<1e-6
    emission_qa=json.loads((L/'lobes/emission-qa.json').read_text());assert emission_qa['pass']
    assert digest(P/'lava-refined.png')=='dab9d6c2f0ca2613b1643a176a2e20e4aa1500c0f87a002a5c7cfd2d0975e4be'
    assert digest(P/'lava-restored-first.png')=='3e1eabbde8653b89b2cbae18b9f965da2b33a5c38e4e5a288aa59cf7ce26826f'
    shutil.copy2(hero.with_suffix('.png'),P/'lava-folded.png');shutil.copy2(detail.with_suffix('.png'),P/'lava-folded-detail.png')
    source=json.loads((L/'lobes/lobes-05.json').read_text())
    source['limits'].append('Lateral cooling near crust edges is an analytic approximation; the column energy residual is not a global 3D energy audit')
    review={'status':'Reviewed CPU material stills; a new procedural morphology study, not a completed simulation film','defaultView':'Folded lava','image':'lava-folded.png','detail':'lava-folded-detail.png','render':hr,'detailRender':dr,'geometry':source,'previousImagesUnchanged':True,'kept':['Three overlapping rounded lobes replacing the flat slab','Irregular nested crust folds with geometry and thickness','Fragmented cooling skin across fresh breakouts','World-space nose apertures without radial pinching','Cool crust banks around hotter molten centers','Back light that avoids broad pink reflections on molten faces'],'rejected':['Evenly spaced manufactured ribs','Smooth blanket-like folds','Glossy bare orange tips','Radial pinching at the parameterization poles','Over-bright crust illumination'],'remaining':['The layout and folds are authored; a new physically validated moving flow is not implemented','Some fold families and breakup patches still show a procedural character','A moving sigil shot and temporal surface stability have not been verified']}
    review['meshQA']=qa
    review['emissionQA']=emission_qa
    review['kept'].append('Continuous interpolated thermal radiance replaces hard per-face temperature bands')
    review['sourceFiles']={name:digest(R/name) for name in ['lava_lobes_cpu.py','lava_lobes_render.py','lava_emission_io.py','lava_lobes_job.py','lava_thermal.py','lava_radiation.py']}
    (L/'active-candidate.json').write_text(json.dumps(review,indent=2));(P/'review.json').write_text(json.dumps(review,indent=2))
    html=(L/'refined-page.html').read_text(encoding='utf-8')
    start=html.index('<nav aria-label="Lava version">');end=html.index('</nav>',start)+len('</nav>')
    views=[('Folded lava','lava-folded.png','Overlapping lobes / folded basalt skin','Ropy dark basalt lava lobes with incandescent breakouts on pitch black',1280,720),('Close-up','lava-folded-detail.png','Close-up / crust and molten breakouts','Close-up of lava crust folds and ragged molten openings on pitch black',1024,717),('Previous pass','lava-refined.png','Previous rough-basalt pass','Earlier rough basalt material study',896,672),('Original','lava-restored-first.png','Original saved rough pass','Original granular lava material study',640,480)]
    buttons='<nav aria-label="Lava version">'+''.join(f'<button type="button" aria-pressed="{str(i==0).lower()}" data-src="{src}" data-caption="{caption}" data-alt="{alt}" data-width="{w}" data-height="{h}">{label}</button>' for i,(label,src,caption,alt,w,h) in enumerate(views))+'</nav>'
    html=html[:start]+buttons+html[end:]
    start=html.index('<figure>');end=html.index('</figure>',start)+len('</figure>')
    figure='<figure><img id="lava" src="lava-folded.png" alt="'+views[0][3]+'" width="1280" height="720"><figcaption><span id="caption" aria-live="polite">'+views[0][2]+'</span><a id="download" href="lava-folded.png" download>Download image</a></figcaption></figure>'
    html=html[:start]+figure+html[end:]
    html=html.replace('Basalt crust / incandescent interior','Folded basalt / molten breakouts').replace('nav{display:flex;gap:6px}','nav{display:flex;gap:6px;flex-wrap:wrap}')
    start=html.index('<details>');end=html.index('</details>',start)+len('</details>')
    notes='<details><summary>Study notes</summary><p>This pass replaces the shallow slab with overlapping lava lobes, nested crust folds and broken cooling skin over a separate molten interior. The openings have thickness and cool banks around their hotter centers.</p><p>These are CPU Mitsuba material stills. The lobe shapes and folds are authored; the cooling calculation does not make this a fully simulated flow. Motion and sigil integration still need their own validation.</p><p>Form reference: <a href="https://www.nps.gov/articles/000/lava-flow-forms.htm">NPS lava flow forms</a>. <a href="review.json">Render and review record</a>. Earlier images are preserved.</p></details>'
    html=html[:start]+notes+html[end:]
    html=html.replace('lava.src=button.dataset.src;','lava.src=button.dataset.src;lava.width=Number(button.dataset.width);lava.height=Number(button.dataset.height);')
    (P/'index.html').write_text(html,encoding='utf-8')
    contract=json.loads((L/'lobes-contract.json').read_text());contract.update(status='Five geometry/material iterations plus a verified emission interpolation correction; new stills published with earlier passes preserved',finalHero=str(hero.with_suffix('.png')),finalDetail=str(detail.with_suffix('.png')),remaining=review['remaining'],validationExtension='High-resolution review exposed per-face temperature bands; a CPU analytic test and continuous-emission correction were necessary before publication');(L/'lobes-contract.json').write_text(json.dumps(contract,indent=2))
    (L/'lobes/REVIEW.md').write_text('''# Folded lava material study

The shallow slab has been replaced by overlapping, rounded lava lobes. Coarse folds alone looked like fabric and evenly spaced ribs looked manufactured, so the retained shape uses nested, curved folds with varying spacing and strength. Thin independent basalt shells have real aperture walls over a separate molten body. Nose masks use world-space fields to remove radial pinching. Thermal emission comes from temperature; the skin columns cool through conduction, radiation and convection, with an approximate lateral boundary layer beside the crust. Back lighting reduces broad white/pink reflections on the molten faces.

The final hero and close-up were inspected directly. The changes improve the relief, silhouette and crust/melt transition; some fold families and breakup patches remain visibly procedural. This is an authored material study, not a validated new fluid simulation or a finished moving sigil. The enthalpy residual describes the one-dimensional columns only; it is not a global energy audit for the assembled geometry.

The earlier rough-basalt and original images remain byte-for-byte intact. All generation, rendering and denoising used the CPU. No GPU workload or video batch was launched.

Reference: [NPS lava flow forms](https://www.nps.gov/articles/000/lava-flow-forms.htm). No external mesh or texture asset was incorporated.

The larger close-up exposed a separate renderer defect: temperature groups assigned a constant radiance to each face, producing visible bands across molten openings. The retained emitter interpolates per-vertex Planck radiance continuously and samples geometry independently of the repeated texture coordinates. CPU checks verify known barycentric colors, radiance divided by sample density, PDF consistency and an occluded light sample. The original grouped-temperature renders remain diagnostic artifacts only.
''',encoding='utf-8')
    print(json.dumps({'page':str(P/'index.html'),'hero':str(P/'lava-folded.png'),'detail':str(P/'lava-folded-detail.png'),'previousImagesUnchanged':True,'sizes':[hr['size'],dr['size']]}))

if __name__=='__main__':main()
