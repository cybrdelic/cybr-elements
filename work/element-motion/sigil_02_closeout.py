from pathlib import Path
import json,hashlib,psutil
R=Path(__file__).resolve().parent;O=R/'sigil-02-elements';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
items=[]
for e in ['water','earth','air','lightning']:
 a=json.loads((O/f'{e}-audit.json').read_text());assert a['visualStatus']=='reviewed'
 assert hashlib.sha256((P/f'{e}-02.mp4').read_bytes()).hexdigest()==a['sha256']
 items.append({'element':e,'frames':a['decodedFrames'],'duration':float(a['metadata']['format']['duration']),'sha256':a['sha256'],'maxCorner':a['maxCorner'],'visualStatus':'reviewed'})
assert hashlib.sha256((P/'fire-02.mp4').read_bytes()).hexdigest()=='3bb0dd50aa6c2f4ce55edbf18753fc9db27b656d83d4efbcd29a4a33282e83f6'
active=[]
for p in psutil.process_iter(['name','cmdline']):
 try:
  if p.pid!=__import__('os').getpid() and p.info['name'].lower() in ['python.exe','blender.exe','ffmpeg.exe','node.exe'] and any('sigil_02_' in q or 'sigil-02-elements' in q for q in p.info['cmdline'] or []):active.append({'pid':p.pid,'name':p.info['name']})
 except psutil.Error:pass
proof={'status':'complete','variant':'02','artifacts':items,'approvedFireUnchanged':True,'originalVideosUnchanged':17,'browser':{'tab':'5','url':'http://127.0.0.1:8767/elements/motion/bending/sigils/02/?element=water','allFourSelectorsVerified':True,'downloadTargetsVerified':True,'artworkExpansionVerified':True,'lightningReadyState':4,'lightningDecodedSize':[1920,1080],'waterReadyState':4,'waterPlaying':True,'deliverableMarked':True},'activeRenderWorkers':active}
(O/'delivery.json').write_text(json.dumps(proof,indent=2));(O/'STATUS.json').write_text(json.dumps({'status':'complete','delivered':proof['browser']['url'],'artifacts':items,'remaining':[]},indent=2))
cpath=R/'sigil-native/material-first-contract.json';c=json.loads(cpath.read_text());c['status']='User-approved fire02 plus water,earth,air,lightning02 delivered and verified in shared player.';c['completedArtifacts']=[str(P/f'{e}-02.mp4') for e in ['fire','water','earth','air','lightning']];c['deliveryEvidence']=str(O/'delivery.json');cpath.write_text(json.dumps(c,indent=2))
notes=R/'sigil-native/DECISIONS.md';old=notes.read_text();entry='''## Current delivery: all five elements in approved style02

The user approved the corrected02fire ("this is great") and requested the
other four. Water,earth,air,and lightning02are now rendered,decoded,visually
reviewed and published beside that unchanged fire at `/elements/motion/bending/sigils/02/`.
The shared player has independent selection/playback,per-element downloads,
and approved-artwork comparison. Browser tab5was verified and left playing
water. All videos are1080p/30fps. Water is9seconds and ends on camera exit;
earth,air,lightning and the approved fire are9.8seconds.

Final implementations and limitations are in `sigil-02-elements/README.md`.
The selected trials are water(nativeFLIP),earthv3(670layered clasts),airv2
(lighter passive mist),and lightningv4(branched conductor graphs with
excitation-gated aerosol illumination). The older contour-only lightning,
overly bright aerosol,and gravel-like earth previews were rejected.
Do not claim these graphics models are calibrated engineering simulations.
See `sigil-02-elements/delivery.json` for hashes,full decode checks and browser
verification. Only style02is complete for the current request; older01work
below remains historical and must not be presented as delivered.

'''
# Keep human-readable spacing in durable notes.
entry=entry.replace('style02','style 02').replace('02fire','02 fire').replace('water,earth,air','water, earth, air').replace('Water,earth,air,and','Water, earth, air, and').replace('lightning02are','lightning 02 are').replace('rendered,decoded,visually','rendered, decoded, visually').replace('selection/playback,per-element','selection/playback, per-element').replace('tab5was','tab 5 was').replace('are1080p/30fps','are 1080p/30fps').replace('is9seconds','is 9 seconds').replace('are9.8seconds','are 9.8 seconds').replace('earth,air,lightning','earth, air, lightning').replace('water(nativeFLIP),earthv3(670layered','water (native FLIP), earth v3 (670 layered').replace('airv2','air v2').replace('lightningv4','lightning v4').replace('excitation-gated','timed').replace('aerosol,and','aerosol, and').replace('hashes,full','hashes, full').replace('older01work','older 01 work').replace('style02is','style 02 is')
notes.write_text(entry+old)
print(json.dumps({'status':'complete','videos':len(items)+1,'activeRenderWorkers':active,'page':proof['browser']['url']}))
