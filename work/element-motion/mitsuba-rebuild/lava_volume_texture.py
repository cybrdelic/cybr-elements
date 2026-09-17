"""CPU object-space pore gradients, independent of a mesh's UV stretch.

Like a baked normal map, gradients are filtered samples of the height field.
They are transformed through dp/du and dp/dv for Mitsuba's bump interface.
"""
import numpy as np,mitsuba as mi,drjit as dr
from scipy.ndimage import gaussian_filter
_CACHE={}

class VolumeBump(mi.Texture):
    def __init__(self,props):
        super().__init__(props);self.height=props['height'];self.gradient=props['gradient']
    def eval_1(self,si,active=True):return self.height.eval_1(si,active)
    def eval(self,si,active=True):return mi.Spectrum(self.eval_1(si,active))
    def eval_3(self,si,active=True):return mi.Color3f(self.eval_1(si,active))
    def eval_1_grad(self,si,active=True):
        g=self.gradient.eval_3(si,active)
        return mi.Vector2f(dr.dot(g,si.dp_du),dr.dot(g,si.dp_dv))
    def mean(self):return .5
    def max(self):return 1.
    def is_spatially_varying(self):return True
    def to_string(self):return 'LavaVolumeBump[CPU object-space pore gradient]'

mi.register_texture('lava_volume_bump',lambda p:VolumeBump(p))

def make_texture(tile=.10,size=128):
    key=(tile,size)
    if key in _CACHE:return _CACHE[key]
    rng=np.random.default_rng(79832)
    raw=rng.normal(size=(size,size,size)).astype('f4')
    broad=gaussian_filter(raw,2.2,mode='wrap');broad/=broad.std()
    fine=gaussian_filter(raw,.70,mode='wrap');fine/=fine.std()
    # Rounded depressions occupy a minority of the glassy rock matrix.
    pit=np.maximum(-broad-.40,0)
    height=np.clip(.64-.12*pit**1.45+.020*fine,.02,.98).astype('f4')
    # xyz gradient channels; ndarray spatial order is z,y,x.
    gradient=np.stack([(np.roll(height,-1,axis=ax)-np.roll(height,1,axis=ax))*(size/(2*tile)) for ax in [2,1,0]],axis=-1).astype('f4')
    transform=mi.ScalarTransform4f().scale(tile)
    volume=mi.load_dict({'type':'gridvolume','grid':mi.VolumeGrid(height[...,None]),'wrap_mode':'repeat','to_world':transform,'raw':True})
    gradient_volume=mi.load_dict({'type':'gridvolume','grid':mi.VolumeGrid(gradient),'wrap_mode':'repeat','to_world':transform,'raw':True})
    _CACHE[key]=mi.load_dict({'type':'lava_volume_bump','height':volume,'gradient':gradient_volume})
    return _CACHE[key]

def test():
    texture=make_texture();si=mi.SurfaceInteraction3f();si.p=mi.Point3f(.0317,.0229,.0523);si.dp_du=mi.Vector3f(1,0,0);si.dp_dv=mi.Vector3f(0,0,1)
    g=np.array(texture.eval_1_grad(si));si.dp_du=mi.Vector3f(3,0,0);si.dp_dv=mi.Vector3f(0,0,.25)
    changed=np.array(texture.eval_1_grad(si));error=float(np.max(abs(changed-g*[3,.25])))
    assert error<1e-4 and np.isfinite(g).all() and np.linalg.norm(g)>1e-5
    first=float(texture.eval_1(si));si.p+=mi.Vector3f(.1,0,0);repeat=float(texture.eval_1(si));assert abs(first-repeat)<1e-5
    return {'device':'CPU','UVBasisChainRuleError':error,'repeatError':abs(first-repeat),'gradient':g.tolist(),'limits':'Filtered object-space gradient map, not subpixel displacement geometry or an exact derivative of trilinear height interpolation'}
