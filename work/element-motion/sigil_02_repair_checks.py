from pathlib import Path
import json,numpy as np,hashlib
R=Path(__file__).resolve().parent;O=R/'sigil-02-repair';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
out={}
for e in ['fire','air']:out[e+'PreservedSha256']=hashlib.sha256((P/f'{e}-02.mp4').read_bytes()).hexdigest()
assert out['firePreservedSha256']=='3bb0dd50aa6c2f4ce55edbf18753fc9db27b656d83d4efbcd29a4a33282e83f6'
assert out['airPreservedSha256']=='80d89a5bd8ccb347da1659b5dcc8f8417db156bffe66759498adab4cb40b7120'
p=O/'earth-transforms.npz'
if p.exists():
 a=np.load(p)['transforms'];assert np.isfinite(a).all();out['earthShape']=list(a.shape)
 # Object order is lexical in Blender. Infer numeric source id from the unique
 # parked starting location instead of treating array order as birth order.
 ids=np.rint((a[0,:,0]-50)/.5).astype(int);rows=json.loads((O/'earth-source.json').read_text());assert sorted(ids.tolist())==list(range(len(rows)))
 distances=[];angular=[]
 for col,k in enumerate(ids):
  birth=1+int(rows[k]['time']*30);f0=min(190,birth+2);f1=min(191,f0+30)
  distances.append(float(np.linalg.norm(a[f1,col,:3]-a[f0,col,:3])))
  angular.append(float(2*np.arccos(np.clip(abs(np.dot(a[f1,col,3:],a[f0,col,3:])),0,1))))
 out['earthOneSecondMotion']={'medianTranslation':float(np.median(distances)),'medianRotationRadians':float(np.median(angular)),'stationaryBodyCount':int(np.sum(np.asarray(distances)<.01))};assert np.median(distances)>.08
p=O/('water-release-particles/manifest.json' if (O/'water-release-particles/manifest.json').exists() else 'water-particles/manifest.json')
if p.exists():
 m=json.loads(p.read_text());frames=m['frames'];assert all(f['finite'] and f['pressure']['converged'] for f in frames)
 assert all(not f['capacityRejected'] and abs(f['sourceVolumeBalance'])<1e-8 for f in frames)
 out['water']={'framesSoFar':len(frames),'complete':m.get('complete',False),'particles':frames[-1]['particles'],'allFinite':True,'allPressureConverged':True,'allSourceAccountingPassed':True}
 if 'release' in str(p):
  baseline=json.loads((O/'water-basin-manifest.json').read_text())['frames'];n=min(136,len(frames))
  assert all(x['particles']==y['particles'] and np.array_equal(x['center'],y['center']) for x,y in zip(baseline[:n],frames[:n]))
  out['water']['formationFramesUnchanged']=n;out['water']['outflowParticles']=frames[-1]['deleted']
  out['water']['outflowPlaneWorldHeight']=(.12-m['origin'][1])/m['spaceScale']
  for f in range(136):
   assert hashlib.sha256((O/f'water-frames/{f:04}.jpg').read_bytes()).digest()==hashlib.sha256((O/f'water-release-frames/{f:04}.jpg').read_bytes()).digest()
  out['water']['formationImageHashesIdentical']=True
  tail=O/'water-ballistic-tail-report.json'
  if tail.exists():
   b=json.loads(tail.read_text());assert all(row['finite'] for row in b['rows']) and b['rows'][-1]['parcels']==0
   assert all(x['parcels']>=y['parcels'] for x,y in zip(b['rows'],b['rows'][1:]))
   out['water']['selectedPrimaryFrames']=b['startFrame']+1;out['water']['selectedFilmFrames']=b['frames']
   out['water']['residualTransport']='Gravity and quadratic drag on unresolved native parcels'
   out['water']['residualFirstEmptyFrame']=b['firstEmptyFrame'];out['water']['residualAllFinite']=True
reports=[json.loads(p.read_text()) for folder in ['water-mesh','water-release-mesh'] for p in (O/folder).glob('*.json') if p.name!='manifest.json']
out['sprayMaximumVolumeError']=max([abs(r.get('sprayVolumeRelativeError',0)) for r in reports] or [0]);assert out['sprayMaximumVolumeError']<1e-5
channels=sorted(O.glob('discharge-train-*-*.npz'))
if channels:
 assert len(channels)==150,len(channels)
 hashes={}
 for file in channels:
  a=np.load(file);p=a['points'];parent=a['parent']
  assert np.isfinite(p).all() and np.all(parent[1:]<np.arange(1,len(parent))) and parent[0]==-1,file.name
  assert np.all(parent[1:]>=0),file.name
  train,event=map(int,file.stem.split('-')[-2:]);hashes.setdefault(event,[]).append(hashlib.sha256(p.tobytes()).hexdigest())
 assert all(len(set(digests))==5 for digests in hashes.values())
 out['lightning']={'networks':len(channels),'allFinite':True,'allConnected':True,'independentFamiliesPerEvent':5}
 lightningReport=O/'lightning-report.json'
 if lightningReport.exists():
  r=json.loads(lightningReport.read_text());assert all(row['finite'] for row in r['aerosol'])
  out['lightning']['aerosolAllFinite']=True
(O/'technical-checks.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
