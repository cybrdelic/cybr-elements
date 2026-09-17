from pathlib import Path
import json, gzip
import numpy as np

B = Path(__file__).resolve().parent
cache = B / 'water-particles'
m = json.loads((cache / 'manifest.json').read_text())
assert m['complete'] and len(m['frames']) == 120
for row in m['frames']:
    f, n = row['frame'], row['particles']
    raw = np.frombuffer(gzip.decompress((cache / f'{f:04}.gz').read_bytes()), '<f4')
    assert len(raw) == n * 6 and np.isfinite(raw).all(), f
    assert row.get('finite', True) and row.get('sourceVolumeBalance', 0) == 0, f
    assert row.get('pressureFailures', 0) == 0, f
report = dict(
    completeFrames=120,
    finitePositionsAndVelocities=True,
    pressureFailures=m['frames'][-1]['pressureFailures'],
    maxPressureRelativeResidual=max(r.get('pressure', {}).get('relativeResidual', 0) for r in m['frames']),
    sourceVolumeBalanceMax=max(abs(r.get('sourceVolumeBalance', 0)) for r in m['frames']),
    totalParticles=m['frames'][-1]['particles'],
    caveat='Nominal particle volume accounting is not a proof of local incompressibility or resolved atomization.'
)
mesh_rows = [json.loads(p.read_text()) for p in sorted((B / 'water-mesh-calibrated').glob('[0-9][0-9][0-9][0-9].json'))]
if len(mesh_rows) == 120:
    assert max(abs(r.get('totalRepresentedVolumeError', 0)) for r in mesh_rows) <= .025
    report['meshFrames'] = 120
    report['maxMeshVolumeError'] = max(abs(r.get('totalRepresentedVolumeError', 0)) for r in mesh_rows)
    report['maxSprayVolumeError'] = max(abs(r.get('sprayVolumeRelativeError', 0)) for r in mesh_rows)
(B / 'water-simulation-validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
