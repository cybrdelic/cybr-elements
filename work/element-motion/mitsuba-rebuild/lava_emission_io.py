"""Continuous per-vertex lava emission, with unbiased geometric light sampling.

Mitsuba's built-in textured area emitter samples UV space. These folded
meshes use repeated material UVs, so use shape sampling instead and evaluate
the interpolated radiance at the sampled surface interaction.
"""
import numpy as np
import mitsuba as mi
import drjit as dr

def ply(path,v,f,normal,uv,radiance,attributes=None):
    unique,inverse=np.unique(f,return_inverse=True)
    v=v[unique];normal=normal[unique];uv=uv[unique];radiance=radiance[unique];f=inverse.reshape(-1,3)
    attributes={} if attributes is None else attributes
    # Mitsuba's PLY reader groups custom channels by postfix, including
    # scalar properties. A bare 'solid' is silently ignored by the reader.
    attribute_columns={}
    for name,value in attributes.items():
        value=np.asarray(value)[unique]
        if value.ndim==1:attribute_columns[name+'_0']=value
        elif value.shape==(len(unique),3):
            for j,channel in enumerate('rgb'):attribute_columns[name+'_'+channel]=value[:,j]
        else:raise ValueError('PLY custom attributes must be scalar or three-component arrays')
    names=['x','y','z','nx','ny','nz','u','v','heat_r','heat_g','heat_b']+list(attribute_columns)
    vertices=np.zeros(len(v),dtype=[(name,'<f4') for name in names])
    for i,name in enumerate(names[:3]):vertices[name]=v[:,i]
    for i,name in enumerate(names[3:6]):vertices[name]=normal[:,i]
    vertices['u']=uv[:,0];vertices['v']=uv[:,1]
    for i,name in enumerate(names[8:11]):vertices[name]=radiance[:,i]
    for name,value in attribute_columns.items():vertices[name]=value
    faces=np.zeros(len(f),dtype=[('size','u1'),('index','<i4',(3,))]);faces['size']=3;faces['index']=f
    header='ply\nformat binary_little_endian 1.0\nelement vertex '+str(len(v))+'\n'+''.join('property float '+name+'\n' for name in names)+'element face '+str(len(f))+'\nproperty list uchar int vertex_indices\nend_header\n'
    with path.open('wb') as file:file.write(header.encode());vertices.tofile(file);faces.tofile(file)

class LavaEmitter(mi.Emitter):
    def __init__(self,props):
        mi.Emitter.__init__(self,props)
        self.m_flags=mi.EmitterFlags.Surface
        self.scene=None
    def set_scene(self,scene):self.scene=scene
    def eval(self,si,active=True):
        if not active or not si.is_valid() or mi.Frame3f.cos_theta(si.wi)<=0:return mi.Color3f(0)
        return self.get_shape().eval_attribute_3('vertex_heat_color',si,active)
    def sample_direction(self,it,sample,active=True):
        ds=self.get_shape().sample_direction(it,sample,active)
        ds.emitter=self
        if not active or ds.pdf<=0 or dr.dot(ds.d,ds.n)>=0:return ds,mi.Color3f(0)
        si=self.scene.ray_intersect(it.spawn_ray(ds.d),active)
        if not si.is_valid() or si.shape!=self.get_shape() or abs(float(dr.norm(si.p-ds.p)))>1e-4:return ds,mi.Color3f(0)
        return ds,self.eval(si,active)/ds.pdf
    def pdf_direction(self,it,ds,active=True):
        if not active or dr.dot(ds.d,ds.n)>=0:return 0.
        return self.get_shape().pdf_direction(it,ds,active)
    def eval_direction(self,it,ds,active=True):
        if not active or dr.dot(ds.d,ds.n)>=0:return mi.Color3f(0)
        si=self.scene.ray_intersect(it.spawn_ray(ds.d),active)
        if not si.is_valid() or si.shape!=self.get_shape() or abs(float(dr.norm(si.p-ds.p)))>1e-4:return mi.Color3f(0)
        return self.eval(si,active)
    def sample_position(self,time,sample,active=True):
        ps=self.get_shape().sample_position(time,sample,active)
        return ps,1/ps.pdf if active and ps.pdf>0 else 0.
    def pdf_position(self,ps,active=True):return self.get_shape().pdf_position(ps,active)
    def bbox(self):return self.get_shape().bbox()
    def to_string(self):return 'LavaEmitter[continuous barycentric radiance, geometric sampling]'

mi.register_emitter('lava_vertex_area',lambda props:LavaEmitter(props))
