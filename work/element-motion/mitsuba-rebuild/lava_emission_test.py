"""Analytic CPU check of interpolation and direct-light sampling."""
from pathlib import Path
import os,json
os.environ['CUDA_VISIBLE_DEVICES']='-1'
import numpy as np,mitsuba as mi,drjit as dr
mi.set_variant('scalar_rgb');dr.set_thread_count(2)
from lava_emission_io import ply
R=Path(__file__).resolve().parent/'lava-focus/lobes'
v=np.array([[0,0,0],[1,0,0],[0,1,0]],'f4');f=np.array([[0,1,2]],'i4');n=np.array([[0,0,1]]*3,'f4');uv=v[:,:2]
path=R/'emission-probe.ply';ply(path,v,f,n,uv,np.eye(3,dtype='f4'))
mesh=mi.load_dict({'type':'ply','filename':str(path),'emitter':{'type':'lava_vertex_area'}})
scene=mi.load_dict({'type':'scene','mesh':mesh});emitter=mesh.emitter();emitter.set_scene(scene);errors=[]
for x,y in [(0.25,0.25),(.1,.7),(.333,.333)]:
    si=scene.ray_intersect(mi.Ray3f([x,y,1],[0,0,-1]));actual=np.array(emitter.eval(si));expected=np.array([1-x-y,x,y]);errors.append(float(np.max(abs(actual-expected))))
it=mi.Interaction3f();it.p=[.25,.25,1];it.time=0.
ds,weight=emitter.sample_direction(it,mi.Point2f(.3,.7));expected=np.array([1-ds.p.x-ds.p.y,ds.p.x,ds.p.y])/ds.pdf
sampling_error=float(np.max(abs(np.array(weight)-expected)));pdf_error=abs(emitter.pdf_direction(it,ds)-ds.pdf)
assert max(errors)<1e-6 and sampling_error<1e-6 and pdf_error<1e-6
blocked=mi.load_dict({'type':'scene','mesh':mesh,'blocker':{'type':'rectangle','to_world':mi.ScalarTransform4f().translate([.5,.5,.5]).scale([1.,1.,1.])}});emitter.set_scene(blocked)
_,blocked_weight=emitter.sample_direction(it,mi.Point2f(.3,.7));assert not np.array(blocked_weight).any()
report={'device':'CPU','barycentricRadianceMaxError':max(errors),'sampleRadianceOverPdfMaxError':sampling_error,'pdfConsistencyError':pdf_error,'occludedSampleZero':True,'tests':'Three analytic ray hits, a sampled surface point, and an occluded sample','pass':True};(R/'emission-qa.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
