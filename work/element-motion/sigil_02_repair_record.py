from pathlib import Path
import json
R=Path(__file__).resolve().parent
B=R/'sigil-02-elements'
reasons={
 'water':'User rejected: static glass-like cutout, insufficient fluid momentum and depth; worst of the three.',
 'earth':'User rejected: gravel arranged as typography, target-pinned movement instead of convincing stone transport.',
 'lightning':'User rejected: persistent wire drawing and overly uniform small branches.'}
p=B/'STATUS.json';s=json.loads(p.read_text());s['status']='reopened-user-rejected';s['remaining']=list(reasons)
for a in s['artifacts']:
 if a['element'] in reasons:a.update(visualStatus='user-rejected',reason=reasons[a['element']])
p.write_text(json.dumps(s,indent=2))
for e,reason in reasons.items():
 p=B/f'{e}-audit.json';a=json.loads(p.read_text());a.update(visualStatus='user-rejected',reason=reason);p.write_text(json.dumps(a,indent=2))
p=R/'sigil-native/material-first-contract.json';s=json.loads(p.read_text());s['status']='Fire02 approved; air retained. Water, earth and lightning02 rejected by user on 2026-09-16; rebuild in isolated candidates.';p.write_text(json.dumps(s,indent=2))
p=R/'sigil-native/DECISIONS.md';old=p.read_text(encoding='utf-8');note='''## 2026-09-16 — user rejection supersedes technical delivery

Water, earth and lightning02 are rejected. Water is the worst. Fire is explicitly approved; preserve fire and air. A successful encode and finite solver are not visual acceptance.

Observed failures: almost motionless glass water; target-pinned gravel typography; permanent wire-like lightning. Do not fix these with roughness, glow or particle-count adjustments. Restore material-specific motion, inspect a short pilot, and only replace a public video after comparison. Preserve full02 source proportions while allowing material to deform and leave them. Avoid making legibility a constraint on all existing material.

'''
if not old.startswith('## 2026-09-16 — user rejection'):p.write_text(note+old,encoding='utf-8')
O=R/'sigil-02-repair';O.mkdir(exist_ok=True)
(O/'contract.json').write_text(json.dumps({'scope':list(reasons),'preserve':['fire','air'],'background':'black','firstGate':'Water: actual fluid transport and silhouette change in a short sequence, before full render','qualityGates':['Full02 artwork informs variable source widths','Fluid rolls and sheds small spray, rather than moving an intact glass glyph','Stone motion comes from momentum and rigid-body contacts, not per-stone target springs','Electrical leaders and brief return strokes; no permanent wire fill'],'pilotIterations':3,'resolution':'CPU simulation previews and selected CPU renders first; 1080p final if pilot warrants it','rejected':reasons},indent=2))
print('Recorded three explicit rejections; preserved approved media.')
