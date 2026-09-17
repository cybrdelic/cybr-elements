"""Rigid-motion and material-coordinate checks on the CPU Mitsuba texture."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import json
from pathlib import Path
import numpy as np
import mitsuba as mi
mi.set_variant('scalar_rgb')
from lava_emission_io import ply
from lava_material_texture import material_attributes,texture

folder=Path(__file__).parent/'lava-focus/mpm/rebuild-25/optics-validation';folder.mkdir(parents=True,exist_ok=True)
rest=np.array([[0,0,0],[.01,0,0],[0,.01,0]],float);f=np.array([[0,1,2]])
tex=texture();values=[]
angle=.7;R=np.array([[np.cos(angle),0,np.sin(angle)],[0,1,0],[-np.sin(angle),0,np.cos(angle)]])
for name,rotation,translation in [('original',np.eye(3),np.zeros(3)),('moved',R,np.array([.014,-.005,.006]))]:
    v=rest@rotation.T+translation;n=np.tile(rotation@np.array([0,0,1.]),(3,1))
    path=folder/(name+'.ply');ply(path,v,f,n,rest[:,:2],np.zeros_like(v),material_attributes(v,rest,f))
    scene=mi.load_dict(dict(type='scene',surface=dict(type='ply',filename=str(path))))
    p=np.array([.0031,.0027,0.])@rotation.T+translation
    ray=mi.Ray3f(mi.Point3f(p+n[0]*.01),mi.Vector3f(-n[0]));si=scene.ray_intersect(ray)
    assert si.is_valid()
    si.dp_du=mi.Vector3f(rotation[:,0]);si.dp_dv=mi.Vector3f(rotation[:,1])
    values.append((float(tex.eval_1(si)),np.array(tex.eval_1_grad(si))))
height_error=abs(values[0][0]-values[1][0]);gradient_error=float(np.max(abs(values[0][1]-values[1][1])))
assert height_error<1e-5 and gradient_error<.01,(height_error,gradient_error)
result=dict(status='pass',device='CPU',renderer=mi.variant(),rigidMotionHeightError=height_error,rigidMotionMaterialGradientError=gradient_error,amplitudeM=.00006,tileM=.008,limits='Subgrid optical approximation; no geometric fractures are added.')
(folder/'proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
