from pathlib import Path
import json,hashlib,gzip,struct,time
import numpy as np
r=Path(__file__).resolve().parents[1]
report={'build':'CYBR FLIP II','scenes':[],'failures':[]};start=time.time()
for name in ['breach','impact','jets','cascade','slosh','vortex','paddle','capillary','viscous']:
 m=json.loads((r/'cache'/name/'manifest.json').read_text());cfg=m['config'];h=cfg['h'];hashes=[];meshhashes=[];finite=True;violations=0;volumeErrors=[];normalErrors=[];count=0;encodedVolume=[]
 for frame,stats in zip(m['frames'],m['meshes'],strict=True):
  i=frame['frame'];raw=(r/'cache'/name/f'{i:04d}.particles').read_bytes();hashes.append(hashlib.sha256(raw).hexdigest());data=np.frombuffer(raw,np.float32);n=frame['particles'];assert len(data)==n*6;p=data[:n*3].reshape(-1,3)
  finite &= bool(np.all(np.isfinite(data)));e=np.array(cfg['extent']);violations+=int(np.count_nonzero(np.any((p<h-1e-5)|(p>e-h+1e-5),axis=1)))
  for o in frame.get('colliders',cfg['obstacles']):
   if o['kind']=='sphere':inside=np.linalg.norm(p-np.array(o['center']),axis=1)<o['radius']-h*.01
   else:inside=np.all(np.abs(p-np.array(o['center']))<np.array(o['half'])-h*.01,axis=1)
   violations+=int(np.count_nonzero(inside))
  assert frame['particles']==frame['initialParticles']+frame['spawned']-frame['deleted'];assert frame['capacityRejected']==0;assert frame['pressure']['converged']
  buf=gzip.decompress((r/'cache'/name/f'{i:04d}.mesh.gz').read_bytes());digest=hashlib.sha256(buf).hexdigest();assert digest==stats['payloadSha256'];meshhashes.append(digest)
  magic,nv,nf,nd,nw,np_,cw,ch=struct.unpack_from('<8I',buf);assert magic==0x43465233;offset=32
  vp=np.frombuffer(buf,np.uint16,nv*3,offset).reshape(-1,3).astype(np.float32)/65535*e;offset+=nv*6
  normal=np.frombuffer(buf,np.int16,nv*3,offset).reshape(-1,3).astype(np.float32)/32767;offset+=nv*6
  normalErrors.append(float(np.max(np.abs(np.linalg.norm(normal,axis=1)-1))) if nv else 0);offset+=nv
  ix=np.frombuffer(buf,np.uint32,nf*3,offset).reshape(-1,3);offset+=nf*12;assert nf==0 or int(ix.max())<nv
  total=0.
  for j in range(0,nf,20000):
   t=vp[ix[j:j+20000]];total+=float(np.einsum('ij,ij->i',t[:,0],np.cross(t[:,1],t[:,2])).sum())/6
  qerr=(abs(total)-stats['targetMeshVolume'])/stats['targetMeshVolume'];encodedVolume.append(qerr)
  offset+=nd*6+nw*24+np_*6+cw*ch*2;assert offset==len(buf)
  volumeErrors.append(stats['meshVolumeRelativeError']);count+=1
 scene={'name':name,'frames':count,'initialParticles':m['frames'][0]['initialParticles'],'finalParticles':m['frames'][-1]['particles'],'maximumParticles':max(f['particles'] for f in m['frames']),'grid':[cfg['nx'],cfg['ny'],cfg['nz']],'h':h,'finiteAllPrimaryStates':finite,'primarySolidViolations':violations,'distinctPrimaryStates':len(set(hashes)),'distinctMeshPayloads':len(set(meshhashes)),'maximumRelativePressureResidual':max(f['pressure']['relativeResidual'] for f in m['frames']),'maximumPressureIterations':max(f['pressure']['iterations'] for f in m['frames']),'maximumMeshVolumeAbsoluteRelativeError':max(map(abs,volumeErrors)),'maximumEncodedMeshVolumeAbsoluteRelativeError':max(map(abs,encodedVolume)),'maximumNormalLengthError':max(normalErrors),'maximumTriangles':max(s['triangles'] for s in m['meshes']),'maximumSecondaryParticles':max(s['secondaryParticles'] for s in m['meshes']),'maximumPrimaryDroplets':max(s['primaryDroplets'] for s in m['meshes']),'primarySha256':hashes,'meshSha256':meshhashes}
 if not finite or violations or count!=120 or len(set(hashes))!=120:report['failures'].append(name)
 report['scenes'].append(scene);print('AUDIT',name,'volume',scene['maximumEncodedMeshVolumeAbsoluteRelativeError'],'states',len(set(hashes)),flush=True)
 report['seconds']=time.time()-start;(r/'tests'/'cache-audit-ii.json').write_text(json.dumps(report,indent=2))
assert not report['failures'];print('ALL STATES VERIFIED',flush=True)
