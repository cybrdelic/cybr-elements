"""Damped elastic waves in a connected rock sample following the shared source.
The floating sample is an authored witness; this is not geological tomography.
"""
from pathlib import Path
import sys,json
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));sys.path.insert(0,str(R.parent))
from scene import *
from shared_motion import pose
s=setup(80);N=420;M=12;ts=np.linspace(.08,1.68,N)
for light in bpy.data.lights:light.energy*=.85
centers=[];normal=[]
for t in ts:
    p,d,_,_=pose(float(t));centers.append([p[0],0,p[1]]);normal.append([-d[1],0,d[0]])
centers=np.array(centers);normal=np.array(normal);u=np.zeros(N);speed=u.copy();ds=np.linalg.norm(np.diff(centers,axis=0),axis=1).mean();rng=np.random.default_rng(718)
# A real finite-difference elastic wave with damping. Source impulses act at the
# moving emitter; the medium transmits displacement to neighboring samples.
history=[]
for frame in range(120):
    for sub in range(32):
        dt=1/960;t=(frame+sub/32)/30;active=ts<=t;lap=np.r_[u[1]-u[0],u[2:]-2*u[1:-1]+u[:-2],u[-2]-u[-1]]/ds**2
        drive=np.exp(-((ts-t)/.028)**2)*np.sin(t*37)*420*(t<1.68)
        speed+=(5.0**2*lap-3.2*speed+drive)*dt;speed[~active]=0;u+=speed*dt;u[~active]=0
    assert np.isfinite(u).all();history.append(u.copy())
mat=material('Fractured basalt',(.075,.069,.06),.82);nd=mat.node_tree.nodes;ln=mat.node_tree.links;bs=nd.get('Principled BSDF');coord=nd.new('ShaderNodeTexCoord');mapping=nd.new('ShaderNodeVectorMath');mapping.operation='SCALE';mapping.inputs[3].default_value=3;ln.new(coord.outputs['Object'],mapping.inputs[0])
for suffix,socket,noncolor in [('diff','Base Color',False),('rough','Roughness',True)]:
    tex=nd.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ASSETS/f'rock_boulder_cracked_{suffix}_2k.jpg'));tex.projection='BOX';tex.projection_blend=.25
    if noncolor:tex.image.colorspace_settings.name='Non-Color'
    ln.new(mapping.outputs[0],tex.inputs['Vector'])
    if suffix=='diff':
        dark=nd.new('ShaderNodeMixRGB');dark.blend_type='MULTIPLY';dark.inputs[0].default_value=1;dark.inputs[2].default_value=(.19,.21,.23,1);ln.new(tex.outputs['Color'],dark.inputs[1]);ln.new(dark.outputs[0],bs.inputs[socket])
    else:ln.new(tex.outputs['Color'],bs.inputs[socket])
tex=nd.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ASSETS/'rock_boulder_cracked_disp_2k.jpg'));tex.image.colorspace_settings.name='Non-Color';tex.projection='BOX';tex.projection_blend=.25;ln.new(mapping.outputs[0],tex.inputs['Vector']);b=nd.new('ShaderNodeBump');b.inputs['Distance'].default_value=.012;b.inputs['Strength'].default_value=.6;ln.new(tex.outputs[0],b.inputs['Height']);ln.new(b.outputs[0],bs.inputs['Normal'])
angles=np.linspace(0,2*np.pi,M,endpoint=False);knots=rng.uniform(.8,1.2,(42,M));rough=np.column_stack([np.interp(np.linspace(0,41,N),np.arange(42),knots[:,j]) for j in range(M)]);faces=[]
for i in range(N-1):
    for j in range(M):faces.append([i*M+j,(i+1)*M+j,(i+1)*M+(j+1)%M,i*M+(j+1)%M])
faces=np.array(faces);old=None
# A granular witness makes the material and traveling displacement visible.
# It replaces the smooth swept sample, which read as a leather ribbon.
grain_count=22000;grain_t=rng.uniform(.08,1.68,grain_count);grain_index=np.clip(np.round((grain_t-.08)/1.6*(N-1)).astype(int),0,N-1);theta=rng.uniform(0,2*np.pi,grain_count);radial=np.sqrt(rng.random(grain_count));grain_rest=centers[grain_index]+normal[grain_index]*(np.cos(theta)*radial*.15)[:,None]+np.array([0,1,0])[None]*(np.sin(theta)*radial*.07)[:,None];grain_r=.007+.020*rng.random(grain_count)**5;rot=rng.uniform(0,6.28,(grain_count,3));scale=rng.uniform(.7,1.2,(grain_count,3))
for f in frames():
    if old is not None:remove(old)
    t=(f+1)/30;active=ts<=min(t,1.68);c=centers+normal*np.array(history[f])[:,None]
    v=c[:,None]+normal[:,None]*(np.cos(angles)[None]*.14*rough)[:,:,None]+np.array([0,1,0])[None,None]*(np.sin(angles)[None]*.065*rough)[:,:,None]
    live=grain_t<=t;gp=grain_rest+normal[grain_index]*np.array(history[f])[grain_index,None]
    release=max(0,t-2.55);gp[:,2]-=.5*9.81*release*release
    old=points('Granular elastic-wave witness',gp[live],grain_r[live],mat,rot[live],scale[live])
    finish(s,'seismic',f)
(R/'seismic-mechanism.json').write_text(json.dumps({'method':'finite-difference damped elastic wave, granular witness','substeps':32,'waveSpeed':5,'grains':grain_count,'maximumDisplacement':float(np.abs(history).max()),'limits':'Authored floating sample; grain motion follows the solved displacement, without a discrete grain-contact solve; not tomography'},indent=2),encoding='utf-8')
