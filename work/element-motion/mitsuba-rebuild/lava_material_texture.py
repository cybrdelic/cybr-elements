"""CPU basalt microrelief evaluated in advected material coordinates.

The texture is optical detail, not damage or resolved geometry. Material
coordinates and their tangential Jacobian are carried by the actual mesh.
Thus translation/rotation of a fragment cannot slide the pores over it.
"""
import numpy as np
import mitsuba as mi
import drjit as dr
from lava_volume_texture import make_texture


def material_attributes(v,rest,f):
    world=np.stack([v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]],axis=2)
    reference=np.stack([rest[f[:,1]]-rest[f[:,0]],rest[f[:,2]]-rest[f[:,0]]],axis=2)
    jacobian=reference@np.linalg.pinv(world,rcond=1e-10)
    weight=np.linalg.norm(np.cross(world[:,:,0],world[:,:,1]),axis=1)
    average=np.zeros((len(v),3,3));total=np.zeros(len(v))
    for corner in range(3):
        np.add.at(average,f[:,corner],jacobian*weight[:,None,None]);np.add.at(total,f[:,corner],weight)
    average/=np.maximum(total,1e-30)[:,None,None]
    return dict(reference=rest,reference_dx=average[:,:,0],reference_dy=average[:,:,1],reference_dz=average[:,:,2])


class MaterialBump(mi.Texture):
    def __init__(self,props):
        super().__init__(props);self.base=props['base']
    def interaction(self,si):
        material=mi.SurfaceInteraction3f(si)
        material.p=si.shape.eval_attribute_3('vertex_reference_color',si)
        return material
    def eval_1(self,si,active=True):
        return self.base.eval_1(self.interaction(si),active)
    def eval(self,si,active=True):return mi.Spectrum(self.eval_1(si,active))
    def eval_3(self,si,active=True):return mi.Color3f(self.eval_1(si,active))
    def eval_1_grad(self,si,active=True):
        material=self.interaction(si)
        def pullback(tangent):
            return sum((si.shape.eval_attribute_3('vertex_reference_d'+axis+'_color',si,active)*tangent[i] for i,axis in enumerate('xyz')),mi.Vector3f(0))
        material.dp_du=pullback(si.dp_du);material.dp_dv=pullback(si.dp_dv)
        return self.base.eval_1_grad(material,active)
    def mean(self):return self.base.mean()
    def max(self):return self.base.max()
    def is_spatially_varying(self):return True
    def to_string(self):return 'LavaMaterialBump[advected reference coordinates, 60 micrometre amplitude]'


mi.register_texture('lava_material_bump',lambda p:MaterialBump(p))


def texture():
    return mi.load_dict(dict(type='lava_material_bump',base=make_texture(tile=.008,size=64)))
