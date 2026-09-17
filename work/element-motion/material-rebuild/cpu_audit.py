"""CPU-only structural audits. Warnings are evidence, not visual approval."""
from pathlib import Path
import sys,json,hashlib,time,numpy as np
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent;D=R.parent/'dynamics';sys.path.insert(0,str(R));sys.path.insert(0,str(D))
from cpu_catalog import catalog
from cache_io import fluid_mesh
OUT=R/'cpu';OUT.mkdir(exist_ok=True);start=time.time()
def triangles(f):
 if isinstance(f,np.ndarray) and f.ndim==2 and f.shape[1]==3:return f.astype('i4')
 return np.array([(face[0],face[j],face[j+1]) for face in f for j in range(1,len(face)-1)],dtype='i4').reshape(-1,3)
def mesh(v,faces):
 v=np.asarray(v);f=triangles(faces);result={'vertices':len(v),'triangles':len(f),'finite':bool(np.isfinite(v).all())}
 if not len(v) or not len(f):return result
 result['validIndices']=bool(f.min()>=0 and f.max()<len(v))
 if not result['validIndices']:return result
 area=np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1)*.5;edges=np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1);_,counts=np.unique(edges,axis=0,return_counts=True)
 result.update(degenerateFaces=int((area<1e-12).sum()),boundaryEdges=int((counts==1).sum()),nonmanifoldEdges=int((counts>2).sum()),signedVolume=float(np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))/6),extent=np.ptp(v,axis=0).tolist())
 return result
rows=[]
for recipe in catalog():
 k=recipe['id'];row={'id':k,'hardErrors':[],'warnings':[recipe['limitation']],'checks':{}}
 if not (R/recipe['script']).exists():row['hardErrors'].append('Missing material recipe')
 try:
  if k in ['lava','ice','metal','foam','blood','mud']:
   for f in [30,45,65,90]:
    if k in ['lava','ice','foam']:
     a=np.load(R/'data'/k/f'{f:04}.npz');v,fa=a['v'],a['f']
    elif k=='metal':
     a=np.load(D/'surface/metal'/f'{f:04}.npz');v,fa=a['v'],a['f']
    else:v,fa,_,_=fluid_mesh(f,k=='mud')
    check=mesh(v,fa);row['checks'][str(f)]=check
    if not check['finite'] or not check.get('validIndices',True):row['hardErrors'].append(f'Invalid geometry at frame {f}')
   if k=='ice':
    a=json.loads((R/'ice-fractures.json').read_text());row['checks']['fractureVolumeCoverage']=a['pieceVolume']/a['sourceVolume'];row['checks']['fracturePieces']=len(a['pieces']);row['checks']['closedPieces']=sum(mesh(p['vertices'],p['faces']).get('boundaryEdges',1)==0 for p in a['pieces'])
   if k=='foam':
    a=np.load(R/'data/foam/0045.npz');p,r=a['p'],a['r'];distance,index=cKDTree(p).query(p,k=2);ratio=distance[:,1]/np.maximum(r+r[index[:,1]],1e-9);row['checks']['cells']={'count':len(p),'radiusQuantiles':np.quantile(r,[0,.5,.95,1]).tolist(),'severeOverlapFraction':float((ratio<.55).mean()),'filmRange':[float(a['film'].min()),float(a['film'].max())]}
  elif k in ['sand','snow']:
   for f in [30,45,65,90]:
    a=np.load(D/'cache'/k/f'{f:04}.npz');J=np.linalg.det(a['F'].astype('f4'));row['checks'][str(f)]={'particles':len(J),'finite':bool(np.isfinite(a['p']).all() and np.isfinite(J).all()),'invertedDeformations':int((J<=0).sum()),'JQuantiles':np.quantile(J,[0,.5,.99,1]).tolist()}
    if not row['checks'][str(f)]['finite']:row['hardErrors'].append('Nonfinite particle/deformation data')
  elif k=='plants':
   a=np.load(D/'cache/plants/rods.npz');ed=a['edges'];p=a['p'];length=a['length'];ratios=[]
   for f in [30,45,65,90]:
    active=(a['birth'][ed]<=((f+1)/30)).all(1);ratio=np.linalg.norm(p[f,ed[active,1]]-p[f,ed[active,0]],axis=1)/np.maximum(length[active],1e-8);ratios.extend(ratio)
   row['checks']['rods']={'points':len(a['rest']),'edges':len(ed),'finite':bool(np.isfinite(p).all()),'stretchQuantiles':np.quantile(ratios,[0,.5,.99,1]).tolist()}
  elif k=='glass':
   a=json.loads((D/'cache/glass-shells.json').read_text());checks=[mesh(p['vertices'],p['faces']) for p in a['parts']];row['checks']={'pieces':len(checks),'closedPieces':sum(x.get('boundaryEdges',1)==0 for x in checks),'connections':len(a['connections']),'finite':all(x['finite'] for x in checks)}
  elif k in ['energy','spirit','flight','heat','sound','pressure']:
   a=np.load(D/'cache'/k/'tracers.npz');P=a['p'];row['checks']={'frames':len(P),'particles':P.shape[1],'finite':bool(np.isfinite(P).all()),'positiveRadii':bool((a['r']>0).all()),'temperatureAvailable':'temperature' in a}
   if not row['checks']['finite']:row['hardErrors'].append('Nonfinite tracer history')
  elif k=='combustion':
   a=np.load(D/'cache/combustion/0052.npz')['fields'];row['checks']={'resolution':list(a.shape),'finite':bool(np.isfinite(a).all()),'minimum':float(a.min()),'maximum':float(a.max())}
  else:row['checks']['sourceExists']=(R/recipe['script']).exists()
 except Exception as e:row['hardErrors'].append(type(e).__name__+': '+str(e))
 row['technicalStatus']='fail' if row['hardErrors'] else 'inspect';rows.append(row)
root=R.parents[2];protected=[root/'work/brand-fire-01.npz',root/'work/brand-fire-02.npz',R.parent/'shared-trail.json',*sorted((root/'outputs/cybrdelic-type/typefaces/vector').glob('*-wordmark.svg'))]
hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected};previous=OUT/'protected.json'
if previous.exists():assert json.loads(previous.read_text())==hashes,'Protected original source changed'
else:previous.write_text(json.dumps(hashes,indent=2))
expected={'work/brand-fire-01.npz':'daa4f6ee0737c9f645cd5e4becf31f8223f6c032dbfcc937d162b72669ad025e','work/brand-fire-02.npz':'6edc246a61a309f016185de92fbfe9a742eff3c65d91fc8e3b88c657b223341a'}
for rel,h in expected.items():assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==h
report={'device':'CPU','seconds':round(time.time()-start,3),'materials':rows,'protectedSources':hashes,'meaning':'Technical inspect status does not imply physical or visual acceptance'};(OUT/'audit.json').write_text(json.dumps(report,indent=2));print('CPU audit',len(rows),'materials;',sum(bool(x['hardErrors']) for x in rows),'technical failures;',report['seconds'],'seconds')
for row in rows:
 if row['hardErrors']:print(row['id'],row['hardErrors'])
