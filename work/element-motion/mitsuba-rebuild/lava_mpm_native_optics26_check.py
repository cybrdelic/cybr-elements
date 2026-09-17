"""Direct native-emission checks on an actual saved MPM mesh, CPU only."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import json,hashlib
import numpy as np
from lava_mpm_native_optics26 import ROOT,mi,radiance


def run():
    source=ROOT/'rebuild-25/thermal-unloaded/state-surface.npz';a=np.load(source)
    folder=source.parent/'native-optical-proof'
    scene=mi.load_dict(dict(type='scene',lava=dict(type='ply',filename=str(folder/'surface.ply'),
        emitter=dict(type='area',radiance=dict(type='bitmap',filename=str(folder/'emission.exr'),raw=True,wrap_mode='clamp')))))
    shape=scene.shapes()[0];f=a['f'];side=int(np.ceil(np.sqrt(len(f))));tile=14;size=side*tile
    rng=np.random.default_rng(26);faces=rng.choice(len(f),min(96,len(f)),replace=False)
    errors=[];position=[];phase=[]
    for face in faces:
        uv=(np.array([(face%side)*tile,(face//side)*tile])+2+(tile-4)/3)/size
        si=shape.eval_parameterization(mi.Point2f(uv));assert si.is_valid();si.wi=mi.Vector3f(0,0,1)
        expected=np.array(radiance(float(a['temperature'][f[face]].mean())))*.94
        value=np.array(shape.emitter().eval(si))
        errors.append(float(np.max(abs(value-expected))/max(float(expected.max()),1e-20)))
        position.append(float(np.linalg.norm(np.array(si.p)-a['v'][f[face]].mean(0))))
        phase.append(abs(float(shape.eval_attribute_1('vertex_solid',si))-float(a['solid'][f[face]].mean())))
    report=dict(status='pass' if max(errors)<.025 and max(position)<1e-7 and max(phase)<1e-4 else 'fail',
        device='CPU',variant=mi.variant(),facesTested=len(faces),maximumEmissionRelativeError=max(errors),maximumPositionErrorM=max(position),maximumPhaseError=max(phase),
        sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),scope='Direct emission, phase and non-overlapping UV parameterization; not visual or motion approval.')
    dest=ROOT/'rebuild-26/atlas-proof/actual-mesh-check.json';dest.write_text(json.dumps(report,indent=2));print(json.dumps(report));assert report['status']=='pass'
    return report


if __name__=='__main__':run()
