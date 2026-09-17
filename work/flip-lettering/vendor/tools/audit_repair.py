"""Independently decode every repaired primary state and surface.

No global-volume result is treated as proof of local mass conservation. The
acceptance limits are fixed before the final Hero simulation has completed.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,struct,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
NAMES=['impact','breach','jets','slosh','hero']
sha=lambda b:hashlib.sha256(b).hexdigest()
def await_manifest(folder,timeout=3600):
 start=time.time()
 while time.time()-start<timeout:
  try:
   m=json.loads((folder/'manifest.json').read_text())
   if m.get('simulationComplete') and len(m.get('frames',[]))==120 and len(m.get('meshes',[]))==120:return m
  except (OSError,ValueError):pass
  time.sleep(2)
 raise TimeoutError(folder)
def audit(names=NAMES):
 started=time.time();rows=[]
 for name in names:
  d=ROOT/'cache'/name;m=await_manifest(d)
  assert m['config']['quality']=='ultra' and m['config']['flip']==.93 and m['config']['separation'] is True
  for file,h in m['sourceHashes'].items():assert sha((ROOT/file).read_bytes())==h,(file,'source changed after simulation')
  stats={'scene':name,'frames':120,'h':m['config']['h'],'grid':[m['config'][x] for x in ['nx','ny','nz']],
    'initialParticles':m['frames'][0]['initialParticles'],'finalParticles':m['frames'][-1]['particles'],
    'maxParticles':0,'maxTriangles':0,'maxPressureResidual':0.,'maxPressureIterations':0,
    'maxNormalLengthError':0.,'maxEncodedGlobalVolumeDiscrepancy':0.,'maxNominalRepresentationVolumeDiscrepancy':0.,
    'maxPrimaryDomainOvershoot':0.,'maxPrimarySolidPenetration':0.,'maximumWhitewater':0,
    'totalPressureSolves':m['frames'][-1]['pressureSolves'],'sourceHashesMatch':True,'geometricInflationFrames':0}
  primary_hashes=set();mesh_hashes=set();ext=np.array(m['config']['extent']);h=m['config']['h']
  for i,(frame,mesh) in enumerate(zip(m['frames'],m['meshes'])):
   raw=(d/f'{i:04d}.particles').read_bytes();shape=(d/f'{i:04d}.shape').read_bytes();payload=gzip.decompress((d/f'{i:04d}.mesh.gz').read_bytes())
   assert sha(raw)==frame['primarySha256'] and sha(shape)==frame['shapeSha256'] and sha(payload)==mesh['payloadSha256']
   n=frame['particles'];a=np.frombuffer(raw,'<f4');s=np.frombuffer(shape,'<f4').reshape(n,6)
   assert len(a)==n*6 and np.isfinite(a).all() and np.isfinite(s).all()
   p=a[:n*3].reshape(n,3);overshoot=max(float(np.max(-p)),float(np.max(p-ext)),0.);assert overshoot<1e-6
   penetration=0.
   for o in frame['colliders']:
    if o['kind']=='sphere':penetration=max(penetration,float(o['radius']-np.linalg.norm(p-np.array(o['center']),axis=1).min()))
    elif o['kind']=='box':
     lo=np.array(o['center'])-np.array(o['half']);hi=np.array(o['center'])+np.array(o['half']);inside=np.all((p>lo)&(p<hi),axis=1)
     if inside.any():penetration=max(penetration,float(np.min(np.minimum(p[inside]-lo,hi-p[inside]),axis=1).max()))
   assert penetration<max(2e-6,h*.002),(name,i,penetration)
   # Independent Sylvester criteria on carried shape history, even though the
   # delivery mesher intentionally does not blend that history into its field.
   xx,yy,zz,xy,xz,yz=s.astype(np.float64).T;minor=xx*yy-xy*xy
   det=xx*yy*zz+2*xy*xz*yz-xx*yz*yz-yy*xz*xz-zz*xy*xy
   assert (xx>0).all() and (minor>0).all() and (det>0).all()
   magic,nv,nf,nd,nw,np_,cw,ch=struct.unpack_from('<8I',payload)
   assert magic==0x43465234 and len(payload)==32+nv*13+nf*12+nd*10+nw*24+np_*6+cw*ch*2
   norm=np.frombuffer(payload,'<i2',nv*3,32+nv*6).reshape(nv,3).astype(np.float64)/32767
   nl=np.linalg.norm(norm,axis=1);assert (nl>.99).all() and (nl<1.01).all()
   f=np.frombuffer(payload,'<u4',nf*3,32+nv*13).reshape(-1,3);assert f.max()<nv
   verts=np.frombuffer(payload,'<u2',nv*3,32).reshape(nv,3).astype(np.float64)/65535*ext
   tri=verts[f];volume=float(np.sum(np.einsum('ij,ij->i',tri[:,0],np.cross(tri[:,1],tri[:,2])))/6)
   target=mesh['targetMeshVolume'];discrepancy=abs(volume-target)/max(target,1e-20)
   assert discrepancy<.003,(name,i,'decoded volume discrepancy exceeds fixed 0.3% acceptance',discrepancy)
   radii=np.frombuffer(payload,'<f4',nd,32+nv*13+nf*12+nd*6);assert np.isfinite(radii).all() and (radii>0).all()
   assert frame['pressure']['converged'] and frame['pressure']['relativeResidual']<=1.0001e-5
   assert frame['particles']==frame['initialParticles']+frame['spawned']-frame['deleted']
   assert mesh['meshedPrimaryMarkers']+mesh['dropletPrimaryMarkers']==n and mesh['primaryRepresentationSetsDisjoint']
   assert mesh['volumeRecovery'] is None and mesh['normalVolumeCorrectionDistance']==0
   assert mesh['temporalFieldBlend']==mesh['shapeHistoryWeight']==0
   total=volume+float((4*np.pi/3*radii.astype(np.float64)**3).sum());nominal=n*(h*.5)**3
   for key,value in [('maxParticles',n),('maxTriangles',nf),('maxPressureResidual',frame['pressure']['relativeResidual']),
      ('maxPressureIterations',frame['pressure']['iterations']),('maxNormalLengthError',float(np.max(abs(nl-1)))),
      ('maxEncodedGlobalVolumeDiscrepancy',discrepancy),('maxNominalRepresentationVolumeDiscrepancy',abs(total/nominal-1)),
      ('maximumWhitewater',nw),('maxPrimaryDomainOvershoot',overshoot),('maxPrimarySolidPenetration',penetration)]:stats[key]=max(stats[key],value)
   primary_hashes.add(frame['primarySha256']);mesh_hashes.add(mesh['payloadSha256'])
  assert len(primary_hashes)==len(mesh_hashes)==120
  stats['distinctPrimaryStates']=len(primary_hashes);stats['distinctMeshes']=len(mesh_hashes);rows.append(stats)
  # Set completion metadata only after the full independent audit establishes it.
  m['meshingComplete']=True;(d/'manifest.json').write_text(json.dumps(m,indent=2))
  print('AUDITED',name,'volume',stats['maxEncodedGlobalVolumeDiscrepancy'],flush=True)
 result={'passed':True,'scenes':rows,'uniquePrimaryStates':sum(x['frames'] for x in rows),
  'totalPressureSolves':sum(x['totalPressureSolves'] for x in rows),'primaryAndShapeHashesRecomputed':True,
  'meshPayloadHashesRecomputed':True,'allNormalsUnitWithinQuantization':True,'allCarriedShapeTensorsSPD':True,
  'sourceHashVerification':True,'acceptance':{'relativePressureResidual':1e-5,'decodedGlobalVolumeError':.003,'geometricInflationFrames':0},
  'qualification':'Volume is measured against assigned constant primary-marker volumes. No local mass-conservation, resolved air, thin-sheet correctness or commercial-parity claim.',
  'wallSeconds':time.time()-started}
 out=ROOT/'tests/repair/cache-audit.json';out.write_text(json.dumps(result,indent=2));print('ALL REPAIR CACHE AUDITS PASS',flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('scenes',nargs='*',default=NAMES);o=a.parse_args();audit(o.scenes or NAMES)
