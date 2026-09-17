"""CPU mesh-attribute check for continuous phase optics."""
import os
os.environ['CUDA_VISIBLE_DEVICES']='-1'
import json,numpy as np,mitsuba as mi
mi.set_variant('scalar_rgb')
from lava_mpm import ROOT
from lava_emission_io import ply

def main():
    folder=ROOT/'validation';path=folder/'phase-optics-triangle.ply'
    v=np.array([[0.,0,0],[1.,0,0],[0.,1,0]]);f=np.array([[0,1,2]])
    ply(path,v,f,np.tile([0.,0,1],(3,1)),v[:,:2],np.tile([.2,.04,.01],(3,1)),{'solid':np.array([0.,.5,1.])})
    def material(alpha):return dict(type='roughplastic',alpha=alpha,int_ior=1.57,diffuse_reflectance=.02)
    shape=mi.load_dict(dict(type='ply',filename=str(path),bsdf={'type':'blendbsdf','weight':{'type':'mesh_attribute','name':'vertex_solid'},'bsdf_0':material(.055),'bsdf_1':material(.48)}))
    scene=mi.load_dict({'type':'scene','shape':shape})
    si=scene.ray_intersect(mi.Ray3f(mi.Point3f(.25,.25,1),mi.Vector3f(0,0,-1)))
    assert si.is_valid()
    phase=float(shape.eval_attribute_1('vertex_solid',si));heat=np.array(shape.eval_attribute_3('vertex_heat_color',si))
    value=np.array(si.bsdf().eval(mi.BSDFContext(),si,mi.Vector3f(0,0,1)))
    assert abs(phase-.375)<1e-7 and abs(heat-[.2,.04,.01]).max()<1e-7 and np.isfinite(value).all() and (value>0).all()
    result=dict(status='pass',renderer='Mitsuba '+mi.__version__,device='CPU',variant=mi.variant(),interpolatedSolid=phase,emissionAttributeError=float(abs(heat-[.2,.04,.01]).max()),normalIncidenceBSDF=value.tolist())
    (folder/'continuous_phase_optics.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':main()
