"""Record actual reviewed delivery, without turning agent review into user approval."""
from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parent;O=R/'sigil-02-repair';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
publication=json.loads((O/'publication.json').read_text())
checks=json.loads((O/'technical-checks.json').read_text());assert checks['water']['complete'] and checks['water']['framesSoFar']==216
browser=json.loads((O/'browser-verification.json').read_text());assert browser['passed']
artifacts=[]
for element in ['water','earth','lightning']:
 a=json.loads((O/f'{element}-audit.json').read_text());assert a['visualStatus']=='reviewed-improvement'
 path=P/f'{element}-02-r2.mp4';assert hashlib.sha256(path.read_bytes()).hexdigest()==a['sha256']
 artifacts.append(dict(element=element,path=str(path),frames=a['frames'],duration=float(a['metadata']['format']['duration']),sha256=a['sha256'],visualStatus='agent-reviewed; user acceptance pending',limitations=a.get('limitations',[])))
status=dict(status='revisions-published-for-user-review',delivered='http://127.0.0.1:8767/elements/motion/bending/sigils/02/?element=water',artifacts=artifacts,preserved=publication['preserved'],previousVersionToggle=True,technicalChecks='technical-checks.json',browserVerification='browser-verification.json',userAccepted=False)
(O/'STATUS.json').write_text(json.dumps(status,indent=2))
legacy=R/'sigil-02-elements/STATUS.json';old=json.loads(legacy.read_text());old['successorReview']=str(O/'STATUS.json');old['status']='superseded-rejected-versions-retained-for-comparison';legacy.write_text(json.dumps(old,indent=2))
contract=R/'sigil-native/material-first-contract.json';c=json.loads(contract.read_text());c['status']='Fire02 approved and unchanged; air retained unchanged. Rebuilt water, earth and lightning02 published for review on 2026-09-16. User acceptance pending.'
c['completedArtifacts']=[str(P/(f'{e}-02-r2.mp4' if e in ['water','earth','lightning'] else f'{e}-02.mp4')) for e in ['fire','water','earth','air','lightning']]
c['deliveryEvidence']=str(O/'STATUS.json');contract.write_text(json.dumps(c,indent=2))
decisions=R/'sigil-native/DECISIONS.md';s=decisions.read_text(encoding='utf-8')
note='''## 2026-09-16 — rebuilt water, earth and lightning02 delivered for review

Water now uses round moving jet sources, native APIC/FLIP transport, reconstructed
surfaces and persistent subgrid spray. A hidden basin rebound found in the first
full encode was corrected with mass-accounted outflow below the camera. The
first136 formation frames are byte-identical. Once the bulk exits, unresolved
residual parcels continue under gravity and drag rather than remaining stuck
in the sparse grid projection. The final film is8seconds and ends black.
Earth uses scanned large stones, native Bullet contact/rotation and fine grains,
without per-stone position springs. Lightning uses independently grown channel
families and brief return-stroke trains with illuminated aerosol.

The revised1080p/30fps files use `-r2` names. All old media remain available via
Previous version. Approved fire and retained air hashes are unchanged. Each
full video was decoded, representative frames visually compared, numerical
integrity checked, and player selection/comparison verified. These are reviewed
revisions, not a claim of photorealism or user acceptance. Exact evidence,
limitations, hashes and source attribution are in `sigil-02-repair/STATUS.json`
and `sigil-02-repair/README.md`. Older completion notes below are historical.

'''
decisions.write_text(note+s,encoding='utf-8')
print('Delivery recorded; old rejection preserved and user acceptance remains pending.')
