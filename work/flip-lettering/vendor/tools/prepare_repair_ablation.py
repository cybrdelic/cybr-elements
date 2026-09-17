"""Controlled 1080p-comparison inputs: change one pipeline stage at a time.

The comparison uses independently simulated, matched-resolution input states.
A common reference mesher and renderer isolate simulation-setting changes. The
legacy III mesher is separately advanced through the same repaired primary
history; that isolates reconstruction, not resolution or camera changes.
"""
from pathlib import Path
import os
for k in ['NUMBA_NUM_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
import gzip,hashlib,json,sys
import numpy as np
from mesh_ii import reconstruct as reference_reconstruct
from mesh_iii import normals_area,encode
from mesh_repair import mesh_scene
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tests/repair/ablation';OUT.mkdir(exist_ok=True,parents=True)
records=[]
def common_mesher(name,frame=48):
    folder=ROOT/'cache'/name;m=json.loads((folder/'manifest.json').read_text());c=m['config'];row=m['frames'][frame]
    raw=(folder/f'{frame:04d}.particles').read_bytes();n=row['particles'];a=np.frombuffer(raw,'<f4');p=a[:n*3].reshape(n,3);v=a[n*3:].reshape(n,3)
    h=c['h'];spacing=h*.45;extent=np.array(c['extent'],np.float32);shape=tuple(np.ceil(extent/spacing).astype(int)+1)
    field,vel,verts,normals,faces,drops,iso,stats=reference_reconstruct(p,v,h,spacing,shape,extent,None)
    # All solver comparisons share the same geometric normal construction and
    # omit secondary particles, avoiding a second changing reconstruction input.
    normals,area=normals_area(verts,faces)
    radii=np.full(len(drops),h*np.cbrt(3/(32*np.pi)),np.float32)
    diagnostic=p[np.linspace(0,n-1,min(26000,n)).astype(int)]
    path=OUT/f'{name}_common.mesh.gz'
    mesh_hash=encode(path,verts,normals,faces,drops,radii,np.empty((0,6),np.float32),diagnostic,extent,np.zeros(len(verts),np.float32),np.zeros((64,64,2),np.uint8))
    item={'id':name+'_common','primaryScene':name,'frame':frame,'physicalTime':row['time'],'primaryParticles':n,
        'meshPath':str(path.relative_to(ROOT)),'primarySha256':hashlib.sha256(raw).hexdigest(),'meshPayloadSha256':mesh_hash,
        'config':c,'metrics':row,'reconstruction':'common II-scale spatial PCA; 0.45h sampling; same geometric normal routine; no secondary particles',
        'initialIsovalue':1.8,'sameCameraFrameCount':120,'stats':stats}
    records.append(item);print('COMMON MESH',name,frame,len(faces),flush=True)
if __name__=='__main__':
    for name in ['impact_reference_ii','impact_legacy','impact']:common_mesher(name)
    # This case needs all 49 states: old III has transported shape/field history.
    mesh_scene('impact','iii',49,0,False,'_old_mesher')
    for name,profile in [('impact','repair'),('impact_old_mesher','iii')]:
        folder=ROOT/'cache'/name;m=json.loads((folder/'manifest.json').read_text());f=48
        mesh=m['meshes'][f]
        records.append({'id':'mesher_'+profile,'primaryScene':'impact','frame':f,'physicalTime':m['frames'][f]['time'],
            'primaryParticles':m['frames'][f]['particles'],'meshPath':str((folder/f'{f:04d}.mesh.gz').relative_to(ROOT)),
            'primarySha256':m['frames'][f]['primarySha256'],'meshPayloadSha256':mesh['payloadSha256'],
            'config':m['config'],'metrics':m['frames'][f],'reconstruction':profile,'sameCameraFrameCount':120,'stats':mesh})
    assert len(set(x['primarySha256'] for x in records[-2:]))==1
    result={'passed':True,'frame':48,'frameDt':1/48,'samePhysicalTimeTolerance':1e-12,
        'rendering':'camera 0 at progress 48/120, native 1920x1080; common repair raster unless shader comparison explicitly says otherwise',
        'notes':['Solver cases are freshly simulated at the identical grid spacing and seed, not the lower-resolution previous movies.',
            'The common mesh cases are independent single-frame reconstructions; no claim of matching the prior published cache byte-for-byte.',
            'Both mesher-only cases use exactly the same repaired primary state bytes; legacy III reconstructs the preceding history.',
            'Comparisons isolate stages, not every parameter inside a stage.'], 'cases':records}
    (OUT/'cases.json').write_text(json.dumps(result,indent=2));print('ABLATION INPUTS COMPLETE',flush=True)
