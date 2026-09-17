"""Publish only complete, decoded clips; keep every frozen original intact."""
from pathlib import Path
import hashlib, json, shutil, subprocess, sys

B = Path(__file__).resolve().parent
P = B.parents[2] / 'outputs/cybrdelic-type/elements/motion/bending'
baseline = json.loads((B / 'baseline/manifest.json').read_text())
for name, expected in baseline['files'].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name
selection = json.loads((B / 'selection.json').read_text())
validation = {}
for kind in selection:
    v = json.loads((B / f'{kind}-validation.json').read_text())
    assert v['decodedFrames'] == 120
    clip = B / f'{kind}-v5.mp4'
    assert hashlib.sha256(clip.read_bytes()).hexdigest() == v['sha256']
    validation[kind] = dict(file=clip.name, frames=120, sha256=v['sha256'], metadata=v['metadata'])
    for ext in ['mp4', 'jpg']:
        shutil.copy2(B / f'{kind}-v5.{ext}', P / f'{kind}-v5.{ext}')
subprocess.run([sys.executable, str(B / 'build-player.py')], check=True)
previous = json.loads((B / 'baseline/provenance.json').read_text(encoding='utf-8'))
report = {
    'revision': 'bending-v5-controlled-comparison',
    'selection': selection,
    'changes': {
        'earth': 'Same 660 Bullet emission states, rigid body parents and camera. Sharper fracture normals, restrained bump, varied roughness, revised lighting and less obscuring dust.',
        'fire': 'Same simulation. Extinction/emission trial retained for comparison; original remains the default because the visual gain was too small.',
        'air': 'Same simulation. Revised volume extinction and side illumination reveal thin wisps and overlapping curls.',
        'water': 'Same native APIC/FLIP solver, shared source centre, camera and optical render. Area-preserving variable nozzle aspect and axial momentum; Weber/support-loss gating of volume-accounted spray.',
        'lightning': 'Moving local 3D point-charge networks, spatially advancing leaders and repeated strokes along established channels. Same camera, optics and approximate aerosol model.'
    },
    'validation': validation,
    'waterValidation': json.loads((B / 'water-simulation-validation.json').read_text()),
    'unchangedBaselineFiles': len(baseline['files']),
    'baselineManifest': str(B / 'baseline/manifest.json'),
    'limitations': [
        'Bending trajectories, forces, lighting and timing are art directed.',
        'Water secondary breakup is a resolution-dependent, volume-accounted model; it is not directly resolved atomization.',
        'Water is less uniform but still reads as a controlled jet; some late spray clumping remains visible.',
        'Lightning uses guided Laplacian growth and approximate aerosol transport, not full plasma electrodynamics.',
        'Earth and air improvements are restrained. Fire trial was not promoted.',
        'All five baseline versions remain playable and downloadable.'
    ],
    'priorRevision': previous
}
(P / 'provenance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
(B / 'publication.json').write_text(json.dumps({'baselineHashesUnchanged': True, 'files': validation, 'selection': selection}, indent=2), encoding='utf-8')
print('Five verified trials published. Original media and source hashes unchanged.')
