"""Publish a reviewed cohesive-crust candidate beside the previous pass."""
from pathlib import Path
import json,hashlib,shutil,argparse
import numpy as np
from PIL import Image

R=Path(__file__).resolve().parent;L=R/'lava-focus';C=L/'cohesive'
P=R.parents[2]/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main(stem,promote):
    source=L/'renders'/stem;image=source.with_suffix('.png');receipt=json.loads(source.with_suffix('.json').read_text())
    assert receipt['device']=='CPU' and receipt['threads']==2
    assert digest(image)==receipt['imageSha256']
    old=P/'lava-refined.png';assert digest(old)=='dab9d6c2f0ca2613b1643a176a2e20e4aa1500c0f87a002a5c7cfd2d0975e4be'
    pixels=np.array(Image.open(image));hdr=np.load(str(source)+'-raw-aov.npz')['color'];background=np.max(np.abs(hdr),axis=-1)==0
    assert background.mean()>.05 and not pixels[background].any()
    shutil.copy2(image,P/'lava-cohesive.png')
    if not (L/'active-candidate-rough-basalt.json').exists():shutil.copy2(L/'active-candidate.json',L/'active-candidate-rough-basalt.json')
    geometry=json.loads((C/'shell-detailed.json').read_text());mechanics=json.loads((C/'shell-03.json').read_text());thermal=json.loads((C/'shell-thermal.json').read_text());qa=json.loads((C/'motion-qa.json').read_text())
    review={'status':'New material candidate; not a finished film or a claim of world-class realism','defaultView':'New build' if promote else 'Previous pass','image':'lava-cohesive.png','render':receipt,'mechanics':mechanics,'thermal':thermal,'geometry':geometry,'motionQA':qa,'blackBackgroundFraction':float(background.mean()),'previousImageUnchanged':True,'kept':['Separate hot core and thick crust shells','Progressive cohesive tearing','Original rough-basalt surface detail','Continuous contours around small vents','Exposure-based cooling and a cool perimeter'],'rejected':['Smooth blanket-like crust','Uniform orange interior','Reheated perimeter ring','Triangle-discarded hole contours','Pink pool reflections and metallic side-light response'],'remaining':['Some crust shapes still look procedural','No crust self-contact or two-way coupling to a fluid solver','Motion has not passed a final-quality render review']}
    (L/'active-candidate.json').write_text(json.dumps(review,indent=2),encoding='utf-8');(P/'review.json').write_text(json.dumps(review,indent=2),encoding='utf-8')
    html=(L/'refined-page.html').read_text(encoding='utf-8')
    html=html.replace('Basalt crust / incandescent interior','Molten interior / fractured crust')
    start=html.index('<nav aria-label="Lava version">');end=html.index('</nav>',start)+len('</nav>')
    buttons='<nav aria-label="Lava version"><button type="button" aria-pressed="'+str(promote).lower()+'" data-src="lava-cohesive.png" data-caption="New build / separate molten core and crust" data-alt="Rough basalt crust with irregular openings into a separate glowing molten interior on black">New build</button><button type="button" aria-pressed="'+str(not promote).lower()+'" data-src="lava-refined.png" data-caption="Previous rough-basalt pass" data-alt="Previous rough-basalt lava material study on black">Previous pass</button><button type="button" aria-pressed="false" data-src="lava-restored-first.png" data-caption="Original saved rough pass" data-alt="Original granular lava baseline on black">Original</button></nav>'
    html=html[:start]+buttons+html[end:]
    if promote:html=html.replace('id="lava" src="lava-refined.png"','id="lava" src="lava-cohesive.png"').replace('id="download" href="lava-refined.png"','id="download" href="lava-cohesive.png"')
    html=html.replace('width="896" height="672"','width="960" height="720"')
    html=html.replace('Refined material study','New build / separate molten core and crust' if promote else 'Previous rough-basalt pass')
    start=html.index('<details>');end=html.index('</details>',start)+len('</details>')
    notes='<details><summary>Study notes</summary><p>The new build separates the molten interior from the crust. Cohesive constraints let the crust tear as the underlying shape rises and drives it forward. The earlier rough basalt detail is carried with that motion; small vents are actual holes through the crust.</p><p>Surface cooling uses the recorded exposure history, with an approximation for heat loss near the edges. The lava foundation drives the crust in one direction: this is not yet a fully coupled liquid and solid simulation. Some forms still look procedural, and collisions between crust pieces remain unfinished.</p><p>CPU simulation, CPU Mitsuba rendering and CPU denoising. The previous images remain unchanged. <a href="review.json">Render and validation record</a>.</p></details>'
    html=html[:start]+notes+html[end:]
    (P/'index.html').write_text(html,encoding='utf-8')
    contract=json.loads((L/'cohesive-contract.json').read_text());contract['status']='Bounded build and visual review complete; remaining realism issues recorded';(L/'cohesive-contract.json').write_text(json.dumps(contract,indent=2))
    note='''# Cohesive lava study

The hot interior is now a separate closed mesh beneath a thick, perforated crust. A CPU XPBD model supplies membrane deformation, irreversible weld failure, flexion, gravity, viscous drag and unilateral foundation contact. The input foundation rises kinematically; this is not two-way fluid/solid coupling. The prior rough-basalt detail is transferred onto that deformation. Large tears follow the mechanics; small vents remain authored from the earlier surface.

The first geometry studies were rejected before path tracing because the crust stayed intact or became a featureless blanket. The first shaded close-up also failed: dropping whole triangles made sawtooth openings, and the lighting produced pink reflected pools. Small vents now use continuous scalar-contour clipping and relaxed boundary curves. The exposed core uses natural enthalpy-column cooling from four motion snapshots and an approximate lateral boundary layer; the older perimeter keeps its temperature cap. The earlier images have not been overwritten.

CPU checks confirm finite state, irreversible failure and zero measured foundation penetration before detail dressing. Crust self-contact, fully coupled fluid forces and final-quality motion are not validated. These limitations and remaining procedural-looking morphology prevent a claim of production or world-class acceptance.

References: [XPBD](https://matthias-research.github.io/pages/publications/XPBD.pdf), [lava inflation](https://www.nps.gov/subjects/volcanoes/basaltic-lava-flows.htm), and [Mitsuba materials](https://mitsuba.readthedocs.io/en/stable/src/generated/plugins_bsdfs.html).

'''
    previous=(L/'REVIEW.md').read_text(encoding='utf-8');(L/'REVIEW.md').write_text(note+'---\n\n'+previous,encoding='utf-8');shutil.copy2(L/'REVIEW.md',P/'notes.md')
    print(json.dumps({'page':str(P/'index.html'),'image':str(P/'lava-cohesive.png'),'size':list(Image.open(image).size),'promoted':promote,'previousPreserved':True,'imageSha256':digest(P/'lava-cohesive.png')}))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stem');ap.add_argument('--promote',action='store_true');a=ap.parse_args();main(a.stem,a.promote)
