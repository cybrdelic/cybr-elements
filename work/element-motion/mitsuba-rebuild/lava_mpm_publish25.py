"""Publish reviewed CPU evidence without advertising unfinished lava as final."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import hashlib,json,shutil
from pathlib import Path
from PIL import Image
from lava_mpm import ROOT,SOURCE_HASHES

HERE=Path(__file__).parent
PUBLIC=HERE.parents[2]/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava/mpm/repairs'


def read(path):return json.loads(path.read_text())


def main():
    out=ROOT/'rebuild-25'
    checks={name:read(path) for name,path in {
        'baseline':ROOT/'rebuild-24/component-validation.json',
        'integration':ROOT/'rebuild-24/integration-validation.json',
        'rebuild25':out/'component-validation.json'}.items()}
    for name,report in checks.items():
        assert report['status']=='pass',(name,report['status'])
        assert report['sourceHashes']==SOURCE_HASHES,(name,'validation is stale')
    optical=read(out/'optics-validation/proof.json');surface=read(out/'surface-validation/proof.json');gaps=read(out/'gap-validation/proof.json')
    assert optical['status']==surface['status']==gaps['status']=='pass'
    count=sum(len(report['tests']) for report in checks.values())
    cooled=read(out/'thermal-unloaded/proof.json');fed=read(out/'fed-contact-batch/proof.json');fed_surface=read(out/'fed-contact-batch/state-surface.json')
    render_dir=out/'thermal-unloaded/optical-proof';render=read(render_dir/'state.json')
    assert hashlib.sha256(Path(render['source']).read_bytes()).hexdigest()==render['sourceSha256'],'Render surface changed after rendering'
    assert render['variant']=='scalar_rgb' and render['device']=='CPU'
    image=Image.open(render_dir/'state.png');assert max(image.size)<=1600
    assert image.getpixel((0,0))==(0,0,0) and image.getpixel((image.width-1,image.height-1))==(0,0,0)
    full_fracture={name:read(out/name/'proof.json') for name in ['notch-0.002-r1','notch-0.001-r1','notch-0.0005-r1']}
    medium=full_fracture['notch-0.001-r1'];fine=full_fracture['notch-0.0005-r1']
    full_temporal=dict(status='not_converged',comparisonTimeS=.12,mediumFineWorkRelativeDifference=abs(medium['workJ']-fine['workJ'])/abs(fine['workJ']),mediumSeparated=medium['oppositeGripsDisconnected'],fineSeparated=fine['oppositeGripsDisconnected'],source='Preserved historical notch screens; not relabeled as current-source validation.',runs=full_fracture)
    report=dict(revision='solver-25',status='incomplete',finishedLava=False,device='CPU',sourceHashes=SOURCE_HASHES,
        componentChecksPassed=count,checks=checks,opticalCoordinates=optical,surfaceReconstruction=surface,measuredGapReconstruction=gaps,
        cooling=cooled,inlet=fed,inletSurface=fed_surface,fullFractureTemporal=full_temporal,render=render,
        visualReview=dict(status='accepted as a diagnostic only',imageSha256=hashlib.sha256((render_dir/'state.png').read_bytes()).hexdigest(),observed='Smooth dark cooling skin with hotter exposed lower material. Voxel terraces and world-fixed pore sliding have been addressed. The physical inlet has failed crust connections but its measured faces are still closed; no gaps have been drawn.',missing='Heavy separated basalt plates, convincing sustained breakup and final shot quality are not demonstrated.'),
        remaining=['Converged full crack opening in time and space','One defensible lava composition across melt, crystal kinetics and ambient-pressure rock fracture','Separated fracture surfaces without cube-cell artifacts','Long inlet flow with stable deformation and resource use','Coupled gas verification and final motion/appearance review'])
    (out/'review.json').write_text(json.dumps(report,indent=2))
    PUBLIC.mkdir(parents=True,exist_ok=True)
    archive=PUBLIC/'solver-24.html'
    if not archive.exists():shutil.copy2(PUBLIC/'index.html',archive)
    for name,source in {'cooling-25.png':render_dir/'state.png','cooling-geometry-25.png':out/'thermal-unloaded/state-surface-diagnostic.png','review-25.json':out/'review.json'}.items():shutil.copy2(source,PUBLIC/name)
    method=f'''# Lava repairs — solver 25

This is ongoing CPU development, not a finished lava simulation. The reviewed Mitsuba image is an optical diagnostic of the saved 22-second cooling state. It is not an image-generator substitute and it is not proof of full fracture or photorealism.

## Corrected mechanisms

- Conservative bounded heat transfer prevents FLIP enthalpy overshoot. Before the correction, a 1450 K source produced particle temperatures above 1467 K without sufficient mechanical heat. The corrected transfer blends conservative PIC and FLIP candidates with one bound-preserving coefficient; it adds numerical diffusion when limiting is necessary.
- Crack release uses accepted damage and the failed endpoint's normal. This prevents trial iterations from alternately tearing and reconnecting topology, and prevents intact neighbours from bridging a failed band.
- Safeguarded Anderson iteration accelerates the same coupled equations. A short comparison reduced iterations from 114 to 23 while keeping damage differences below 2.3e-7.
- Pressure cells are eliminated before Coulomb contact. Factor lifetimes and response RHS batches reduce memory peaks. Unloaded friction cones use the already-converged normal solution. Long fragmented flows remain unverified.
- The new natural-flow driver uses a published dry-melt viscosity relation and a separate glass-free basalt power-creep reference. Isochoric rock creep does not relax hydrostatic strain.
- Unbroken crystallizing material retains a smooth volume-constrained surface. Solid fraction alone no longer changes it to exposed quadrature cubes. The final hybrid path surfaces the liquid from density and subtracts only the actual positive gaps between separated coherent faces. An analytic 120 micrometre opening is reproduced without widening, with removed-volume error below 3.2e-24 cubic metres. Closed and compressed faces do not produce cuts. This also avoids representing the five inverted liquid inlet cells as solid surface geometry. The former bounded exterior-projection experiment remains a diagnostic, not the final surfacing path.
- Optical microrelief uses persistent material coordinates and their tangential Jacobian. Its nominal amplitude is 60 micrometres, replacing the former 1.1 mm world-space bump. Phase roughness is interpolated continuously. This optical detail does not create cracks.

## Evidence and limits

{count} current-source component/integration checks pass, plus separate material-coordinate and surface-continuity checks. These checks do not certify the complete lava shot.

The cooled lobe reaches 22 seconds, with approximately 17% maximum continuum damage and no separated cracks. The physical inlet test has reached {fed['time']:.4f} seconds with maximum damage {fed['maximumDamage']:.4f}, {fed['brokenEdges']} broken connectivity edges, and mass error {fed['massErrorKg']:.3g} kg. Its last status is {fed['status']}: {fed['error']}.

A historical notched specimen opens completely at the finer tested timestep, but the medium/fine work values differ by {full_temporal['mediumFineWorkRelativeDifference']:.1%} and crack connectivity differs. Full-fracture temporal convergence is therefore not passed. Spatial convergence is not established.

The melt and solid reference laws are from different experiments. The rock power law was measured at 300 MPa confinement; free-surface use is an extrapolation. Crystal fraction, fracture parameters and crystallization kinetics are not composition-calibrated. The current render is a small CPU check, not a final-quality image.

## Primary references

- [Farrell et al. — experimental lava viscosity, Eq. 3](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2019JB018815)
- [Violay et al. — basalt brittle–ductile transition, Table 4](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2011JB008884)
- [Storvik et al. — accelerated staggered phase-field scheme](https://arxiv.org/pdf/2008.11787)

## Reproduction

Use the local `.venv/Scripts/python.exe` and run the CPU jobs sequentially. No GPU renderer or Houdini is used. `lava_mpm_inflation25.py --name fed-contact-batch --until 10 --wall 180 --dt 0.15` resumes only with unchanged solver hashes. `lava_mpm_rebuild25_check.py`, `lava_mpm_rebuild_suite.py` and `lava_mpm_rebuild_smoke.py` produce current-source numerical checks. `lava_mpm_surface25_check.py` and `lava_material_texture_check.py` cover the surface and optical repairs. Incomplete screening runs save accepted state and return a nonzero exit status.
'''
    (PUBLIC/'method-25.md').write_text(method,encoding='utf-8')
    html=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cybrdelic — lava development</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#000;color:#ded3c9;font:15px/1.6 system-ui}}main{{max-width:1120px;margin:auto;padding:26px 4% 64px}}header{{display:flex;justify-content:space-between;border-bottom:1px solid #32281f;padding-bottom:16px;font-size:11px;letter-spacing:.13em}}a{{color:#d8a478}}h1{{font-size:clamp(32px,5vw,52px);font-weight:450;letter-spacing:-.04em;line-height:1.12;margin:34px 0 18px}}p{{max-width:840px;color:#b8aca1}}.notice{{border-left:2px solid #b57c51;padding:10px 18px;margin:24px 0}}figure{{margin:24px 0}}img{{display:block;width:100%;height:auto;background:#000}}.beauty{{max-width:900px;margin:auto}}figcaption,footer{{font-size:12px;color:#a39589}}figcaption{{margin-top:10px}}details{{margin:30px 0;border-top:1px solid #32281f;padding-top:20px}}summary{{cursor:pointer}}li{{margin:.4em 0}}strong{{font-weight:550;color:#ded3c9}}
</style><main><header><span>CYBRDELIC / LAVA</span><a href="../">Lava studies</a></header><h1>Lava development.</h1><p>The cooling surface now stays smooth as crust forms. Heat transfer stays bounded, and the rock detail moves with the material.</p><figure class="beauty"><img src="cooling-25.png" width="640" height="400" alt="CPU Mitsuba diagnostic of a dark cooling lava lobe with hotter glowing material beneath it"><figcaption>Actual saved MPM state at 22 seconds · Mitsuba CPU · Black backdrop · Small optical diagnostic</figcaption></figure><p class="notice"><strong>The finished fractured-lava result is still unresolved.</strong><br>This image verifies surface and material changes. It does not yet show the heavy separated basalt plates, sustained breakup or final motion quality.</p><details><summary>Current simulation evidence</summary><p>The physical inlet has reached {fed['time']:.2f} seconds. Its maximum continuum damage is {fed['maximumDamage']:.1%}; it has {fed['brokenEdges']} broken connectivity edges. Full fracture convergence remains unverified.</p><p>{count} current-source component and integration checks pass. Separate tests verify bounded heat transfer, material-attached texture coordinates, and unchanged exterior geometry when unbroken material crystallizes. These are numerical checks, not a finished-shot quality score.</p><figure><img src="cooling-geometry-25.png" width="1440" height="900" alt="CPU geometry, temperature, solid fraction and damage diagnostics"><figcaption>Diagnostic colors expose the actual coarse simulation state.</figcaption></figure></details><footer>CPU only · <a href="review-25.json">Measured evidence and limitations</a> · <a href="method-25.md">Method</a> · <a href="solver-24.html">Previous solver review</a></footer></main></html>'''
    (PUBLIC/'index.html').write_text(html,encoding='utf-8')
    print(json.dumps(dict(status='published diagnostic; lava unfinished',directory=str(PUBLIC),componentChecksPassed=count,imageSize=image.size,inletTime=fed['time'],brokenEdges=fed['brokenEdges'])))


if __name__=='__main__':main()
