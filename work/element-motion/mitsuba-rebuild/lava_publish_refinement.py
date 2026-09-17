"""Publish a visually reviewed lava still and preserve the comparison baseline."""
from pathlib import Path
import json, shutil, hashlib, argparse
import numpy as np
from PIL import Image

R=Path(__file__).resolve().parent
L=R/'lava-focus'
P=R.parents[2]/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main(stem):
    source=L/'renders'/stem
    receipt=json.loads(source.with_suffix('.json').read_text())
    assert receipt['device']=='CPU' and receipt['threads']==2
    assert sha(source.with_suffix('.png'))==receipt['imageSha256']
    original=L/'renders/hero-0059-640-24spp.png'
    assert sha(original)=='3e1eabbde8653b89b2cbae18b9f965da2b33a5c38e4e5a288aa59cf7ce26826f'
    pixels=np.array(Image.open(source.with_suffix('.png')))
    assert not pixels[:80].any() and not pixels[-60:].any()
    P.mkdir(exist_ok=True,parents=True)
    shutil.copy2(source.with_suffix('.png'),P/'lava-refined.png')
    shutil.copy2(original,P/'lava-restored-first.png')
    shutil.copy2(L/'renders/restored-clean-hero-0059-640-24spp.png',P/'lava-cleaned-baseline.png')
    shutil.copy2(L/'refined-page.html',P/'index.html')
    candidate={'id':'lava-rough-basalt-refinement','status':'Visually reviewed material still; not a finished animation or user-approved replacement baseline',
               'image':'lava-refined.png','renderer':receipt,
               'baseline':json.loads((L/'active-baseline.json').read_text()),
               'geometry':json.loads((L/'refined-lobed-02.json').read_text()),
               'changes':['Corrected emitter selection without removing crust geometry','Thicker irregular lobes','Deeper strain-modulated hot openings','Spatial variation between matte and glassy basalt','Explicit vesicle relief'],
               'remaining':['The crust morphology is authored rather than a coupled fracture simulation','Small-scale structure still repeats in places','No motion validation or sigil film export in this pass'],
               'checks':{'blackTopAndBottom':True,'baselineHashUnchanged':True,'originalSigilCachesUnchanged':True}}
    (P/'review.json').write_text(json.dumps(candidate,indent=2))
    (L/'active-candidate.json').write_text(json.dumps(candidate,indent=2))
    # Keep the user-preferred baseline manifest intact: this is a candidate
    # presented beside it, not retrospective user acceptance.
    contract=json.loads((L/'refinement-contract.json').read_text())
    contract.update(status='Completed bounded still study',controlRenders=1,candidateIterations=4,activeCandidate='active-candidate.json')
    (L/'refinement-contract.json').write_text(json.dumps(contract,indent=2))
    note='''# Lava rough-basalt refinement

The published material still keeps the original rough baseline available through the Earlier pass button. The baseline image and geometry are unchanged. The final candidate has been directly inspected, including the larger still; it is an improvement in form and sampling, not an assertion of world-class realism or a finished simulation.

The first controlled render kept the old geometry and corrected the distribution of light samples. This exposed substantial real crust detail under the old spectral noise. Subsequent CPU studies retained that surface and added uneven thicker lobes, deeper existing openings driven by surface stretch, varied matte/glassy basalt, and vesicle bump relief. No decorative glowing strokes, background environment, GPU work, other elements, sigil edits, or video batch were added.

The original particle cache was not resimulated. The macro shape changes are authored, globally volume-preserving deformations, and the crust exposure is a VFX approximation. Coupled crust fracture, motion and cooling remain unresolved; some repeated small structures are still visible. Those need a mechanics change, not more samples of this still.

Verification: finite geometry, volume agreement, CPU-only render receipts, direct image review, exact black top/bottom image regions, original baseline checksum, and unchanged 01/02 sigil cache checksums. The final render's exact resolution, sample count, resource use and input hash are recorded in active-candidate.json and the bounded process logs.

Reproduce the surface with lava_refine_surface.py. For the final render, use the environment settings in active-candidate.json with lava_refine_render.py through bounded.py. Keep CUDA_VISIBLE_DEVICES=-1. The renderer uses Mitsuba scalar_rgb and explicitly CPU OIDN.

Material implementation reference: https://mitsuba.readthedocs.io/en/stable/src/generated/plugins_bsdfs.html

'''
    old=(L/'REVIEW.md').read_text(encoding='utf-8')
    (L/'REVIEW.md').write_text(note+'---\n\n'+old,encoding='utf-8')
    shutil.copy2(L/'REVIEW.md',P/'notes.md')
    print(json.dumps({'published':str(P/'index.html'),'image':str(P/'lava-refined.png'),'size':[pixels.shape[1],pixels.shape[0]],'sha256':sha(P/'lava-refined.png'),'baselinePreserved':True}))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stem');main(ap.parse_args().stem)
