"""Check vertex emitter energy against Mitsuba's built-in area emitter."""
from pathlib import Path
import numpy as np,json
from lava_relief36 import mi,register_emitter,write_mesh
mi.set_variant('cuda_ad_rgb');register_emitter();T=mi.ScalarTransform4f
folder=Path('lava-focus/mpm/rebuild-32');p=folder/'emitter-check.ply'
v=np.array([[-1,-1,2],[0,1,2],[1,-1,2.]])
write_mesh(p,v,np.array([[0,1,2]]),np.tile([0.,0.,-1.],(3,1)),np.tile([2.,1.,.4],(3,1)),np.zeros(3))
def capture(custom):
    emitter=dict(type='vertex_area36') if custom else dict(type='area',radiance=dict(type='rgb',value=[2.,1.,.4]))
    scene=mi.load_dict(dict(type='scene',integrator=dict(type='path',max_depth=3),sensor=dict(type='perspective',to_world=T().look_at(origin=[0,-4,2],target=[0,0,0],up=[0,0,1]),fov=45.,sampler=dict(type='independent'),film=dict(type='hdrfilm',width=128,height=96,rfilter=dict(type='box'))),light=dict(type='ply',filename=str(p),emitter=emitter),floor=dict(type='rectangle',to_world=T().scale(3),bsdf=dict(type='diffuse',reflectance=.5))))
    for e in scene.emitters():
        if hasattr(e,'set_scene'):e.set_scene(scene)
    return np.array(mi.render(scene,spp=2048,seed=36))
reference=capture(False);candidate=capture(True)
relative=float(np.linalg.norm(candidate-reference)/np.linalg.norm(reference))
energy=float(abs(candidate.sum()-reference.sum())/reference.sum())
assert relative<.025 and energy<.005,(relative,energy)
report=dict(status='pass',comparison='Mitsuba native area emitter, same constant Planck-like RGB and geometric light distribution',imageRelativeL2=relative,totalRadianceRelativeError=energy,spp=2048)
(folder/'emitter36-proof.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
