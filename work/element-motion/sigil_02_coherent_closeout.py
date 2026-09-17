"""Record verified delivery without converting agent review into user approval."""
from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parent;O=R/'sigil-02-coherent';W=R/'sigil-02-water-hold';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
publication=json.loads((O/'publication.json').read_text());browser=json.loads((O/'browser-verification.json').read_text());assert browser['passed']
m=json.loads((W/'particles/manifest.json').read_text());assert m['complete'] and len(m['frames'])==300
assert all(f['finite'] and f['pressure']['converged'] and not f['capacityRejected'] and abs(f['sourceVolumeBalance'])<1e-8 for f in m['frames'])
reports=[json.loads(p.read_text()) for p in sorted((W/'mesh').glob('0*.json'))];assert len(reports)==300
hold=[q for q in reports if 60<=q['frame']<=174]
checks=dict(nativeFrames=300,finitePressureConverged=True,allEmittedParcelsAccounted=True,lastParticleCount=m['frames'][-1]['particles'],firstEmptyFrameAfterWriting=next(f['frame'] for f in m['frames'][60:] if f['particles']==0),maxUnresolvedHoldFraction=max(q['unresolvedMarkerFraction'] for q in hold),renderedAnalyticDrops=sum(q['renderedDrops'] for q in reports),surfaceRepresentation='Resolved fluid mesh; under-resolved isolated markers omitted optically and retained in physical accounting',cachePositionMaxErrorNative=max(m['config']['extent'])/65535/2,cacheVelocityMaxErrorNative=16/32767/2)
(W/'technical-checks.json').write_text(json.dumps(checks,indent=2))
for a in publication['artifacts']:
 e=a['element'];audit=json.loads((O/f'{e}-audit.json').read_text());assert audit['visualStatus']=='agent-reviewed-improvement';assert hashlib.sha256(Path(a['path']).read_bytes()).hexdigest()==audit['sha256']
status=dict(status='revised-videos-published-for-user-review',request='Water, earth and lightning should retain the clean and legible silhouette of fire and smoke; water needs longer hold and no particle-looking drops',url='http://127.0.0.1:8767/elements/motion/bending/sigils/02/?element=water',artifacts=publication['artifacts'],preserved=publication['preserved'],holdUntil=5.8,previousVersion='All three compare against r2; original versions also retained',browserVerification='browser-verification.json',waterTechnicalChecks='../sigil-02-water-hold/technical-checks.json',userAccepted=False)
(O/'STATUS.json').write_text(json.dumps(status,indent=2))
water=json.loads((W/'STATUS.json').read_text());water.update(status='Published water-r3 for user review',deliveryEvidence='../sigil-02-coherent/STATUS.json',changes=['Full rounded artwork volume and exterior bending force','Hold to5.8s, gradual field/gravity release to6.65s','Resolved native surface, no analytic sphere spray','Analytic subgrid capillary optical normals and broad studio refraction fill'],userAccepted=False);(W/'STATUS.json').write_text(json.dumps(water,indent=2))
p=R/'sigil-02-repair/STATUS.json';old=json.loads(p.read_text());old['status']='r2 versions rejected by user; retained as comparison';old['successorReview']=str(O/'STATUS.json');p.write_text(json.dumps(old,indent=2))
p=R/'sigil-native/material-first-contract.json';old=json.loads(p.read_text());old['status']='Fire02 approved and unchanged; air/smoke retained unchanged. Coherent water, earth and lightning r3 published for user review. User acceptance pending.';old['completedArtifacts']=[str(P/(f'{e}-02-r3.mp4' if e in ['water','earth','lightning'] else f'{e}-02.mp4')) for e in ['fire','water','earth','air','lightning']];old['deliveryEvidence']=str(O/'STATUS.json');p.write_text(json.dumps(old,indent=2))
p=R/'sigil-native/DECISIONS.md';s=p.read_text(encoding='utf-8');note='''## 2026-09-16 — full 02 silhouette and longer hold

The user rejected water r2 for losing its form and particle-like spray, then
asked water, earth and lightning to match the clean silhouette of fire and
air/smoke. Revisions now use the full broad artwork and hold through5.8s.
Water uses a full rounded source volume, guided native APIC/FLIP, resolved
surfaces and no analytic sphere cloud. Earth uses interlocking fracture
assembly/hold and Bullet release. Lightning uses contained fine channel
families with a sustained energized silhouette. All three are10s1080p30fps.
Physical versus authored parts and representation limits are documented in
`sigil-02-coherent/README.md`. Fire and air are byte-identical. New r3 media
and browser controls were reviewed; r2 is available through Previous version.
User acceptance remains pending. Evidence: `sigil-02-coherent/STATUS.json`.

'''
if not s.startswith(note):p.write_text(note+s,encoding='utf-8')
print(json.dumps(dict(status=status['status'],waterChecks=checks)))
