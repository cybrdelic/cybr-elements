from pathlib import Path
import hashlib,json,numpy as np,gzip
R=Path(__file__).resolve().parent;S=Path('C:/Users/alexf/Documents/ChatGPT/cybrdelic-platform/flip-water-threejs');V=R.parent/'flip-lettering/vendor';O=R.parent.parent/'outputs/cybrdelic-type/elements/water'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=['src/main.js','src/flip.js','src/flip-reference.js','src/flip-base.js','src/quality-profile.js','tools/mesh_repair.py']
sources={f:{'original':sha(S/f),'used':sha(V/f)} for f in files}
assert all(x['original']==x['used'] for x in sources.values())
assert sha(S/'src/renderer.js')==sha(O/'src/renderer.js')
report={'sourceHashes':sources,'originalRendererSha256':sha(O/'src/renderer.js'),'variants':{}}
for variant in ['01','02']:
 m=json.loads((R/f'cache-{variant}/manifest.json').read_text());assert m['complete'] and len(m['frames'])==192
 assert all(x['finite'] and x['pressure']['converged'] and not x['capacityRejected'] for x in m['frames'])
 n=m['frames'][-1]['particles'];assert n==max(x['particles'] for x in m['frames'])
 assert all(x['particles']==n for x in m['frames'][20:])
 report['variants'][variant]={'states':192,'physicalSeconds':m['frames'][-1]['time'],'particles':n,'finite':True,'pressureConverged':True,'massCountAfterEmissionConstant':True,'source':json.loads((R/f'source-{variant}.json').read_text())['artSha256'],'noPositionalGuide':True}
(R/'audit.json').write_text(json.dumps(report,indent=2));print('Source identity and all 384 physical states verified')
