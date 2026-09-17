import sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from scene import *
K=sys.argv[sys.argv.index('--kind')+1];s=setup(112)
mat=material(K,(.965,.985,1) if K=='ice' else (.93,.98,.96) if K=='glass' else (.009,.006,.004),.03 if K!='lava' else .83,trans=1 if K!='lava' else 0,ior=1.31 if K=='ice' else 1.52)
n=mat.node_tree.nodes;l=mat.node_tree.links;p=n.get('Principled BSDF')
if K in ['ice','glass']:
    # A dim photographic environment lights secondary rays only. Camera pixels
    # retain the black world; there is no visible reference panel or floor.
    wn=s.world.node_tree.nodes;wl=s.world.node_tree.links;wo=wn.get('World Output');ray=wn.new('ShaderNodeLightPath');mix=wn.new('ShaderNodeMixShader');env=wn.new('ShaderNodeBackground');tex=wn.new('ShaderNodeTexEnvironment');tex.image=bpy.data.images.load(str(ASSETS/'studio_small_08_2k.exr'));env.inputs['Strength'].default_value=.18;wl.new(tex.outputs[0],env.inputs[0]);wl.new(ray.outputs['Is Camera Ray'],mix.inputs[0]);wl.new(env.outputs[0],mix.inputs[1]);wl.new(wn.get('Background').outputs[0],mix.inputs[2]);wl.new(mix.outputs[0],wo.inputs[0])
    wl.new(ray.outputs['Is Reflection Ray'],mix.inputs[0]);wl.new(wn.get('Background').outputs[0],mix.inputs[1]);wl.new(env.outputs[0],mix.inputs[2])
    a=n.new('ShaderNodeVolumeAbsorption');a.inputs['Color'].default_value=(.65,.85,.96,1) if K=='ice' else (.66,.88,.74,1);a.inputs['Density'].default_value=.18 if K=='ice' else .5;l.new(a.outputs[0],n.get('Material Output').inputs['Volume'])
    no=n.new('ShaderNodeTexNoise');no.inputs['Scale'].default_value=155;no.inputs['Detail'].default_value=2
    b=n.new('ShaderNodeBump');b.inputs['Distance'].default_value=.0007 if K=='ice' else .00008;b.inputs['Strength'].default_value=.25;l.new(no.outputs['Fac'],b.inputs['Height']);l.new(b.outputs[0],p.inputs['Normal'])
    bubble=material('Trapped air interfaces',(.99,.99,1),.025,trans=1,ior=1/1.31)
    frost=material('Localized frozen microfractures',(.64,.76,.83),.42,trans=.2,ior=1.31)
    if K=='ice':
        for light in bpy.data.lights:light.energy*=.52
        tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ASSETS/'ice002/Ice002_2K-JPG_Roughness.jpg'));tex.image.colorspace_settings.name='Non-Color'
        scale=n.new('ShaderNodeMath');scale.operation='MULTIPLY_ADD';scale.inputs[1].default_value=.22;scale.inputs[2].default_value=.018;l.new(tex.outputs['Color'],scale.inputs[0]);l.new(scale.outputs[0],p.inputs['Roughness'])
        normaltex=n.new('ShaderNodeTexImage');normaltex.image=bpy.data.images.load(str(ASSETS/'ice002/Ice002_2K-JPG_NormalGL.jpg'));normaltex.image.colorspace_settings.name='Non-Color';nm=n.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=.45;l.new(normaltex.outputs[0],nm.inputs['Color']);l.new(nm.outputs[0],p.inputs['Normal'])
        scatter=n.new('ShaderNodeMath');scatter.operation='MULTIPLY_ADD';scatter.inputs[1].default_value=-.5;scatter.inputs[2].default_value=1;l.new(tex.outputs['Color'],scatter.inputs[0]);l.new(scatter.outputs[0],p.inputs['Transmission Weight'])
else:
    heat=n.new('ShaderNodeVertexColor');heat.layer_name='thermal';ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.38;ramp.color_ramp.elements[0].color=(.00001,0,0,1);ramp.color_ramp.elements[1].position=.92;ramp.color_ramp.elements[1].color=(1,.26,.008,1);e=ramp.color_ramp.elements.new(.67);e.color=(.48,.018,.0002,1);l.new(heat.outputs['Color'],ramp.inputs[0]);l.new(ramp.outputs['Color'],p.inputs['Emission Color']);p.inputs['Emission Strength'].default_value=5
    for light in bpy.data.lights:light.energy*=.22
    p.inputs['Emission Strength'].default_value=2.0
    no=n.new('ShaderNodeTexNoise');no.inputs['Scale'].default_value=85;no.inputs['Detail'].default_value=4;b=n.new('ShaderNodeBump');b.inputs['Distance'].default_value=.012;b.inputs['Strength'].default_value=.45;l.new(no.outputs['Fac'],b.inputs['Height']);l.new(b.outputs[0],p.inputs['Normal']);glare(s,2.5,-.94)
    crust=material('Cooled fractured basalt',(.018,.014,.010),.9)
    thermal_mats=[]
    for j in range(64):
        h=(j+.5)/64;temp=400+1150*h
        tm=material('Lava enthalpy '+str(j),(.009,.006,.004),.76)
        tn=tm.node_tree.nodes;tl=tm.node_tree.links;tb=tn.get('Principled BSDF');bb=tn.new('ShaderNodeBlackbody');bb.inputs[0].default_value=temp;tl.new(bb.outputs[0],tb.inputs['Emission Color'])
        tb.inputs['Emission Strength'].default_value=1.2*max(0,(temp-850)/700)**4
        thermal_mats.append(tm)
objects=[]
for f in frames():
    for o in objects:remove(o)
    objects=[];a=np.load(R/'surface'/K/f'{f:04}.npz');v=a['v'];fa=a['f']
    if len(v):
        ob=mesh('Simulated '+K,v,fa,mat,True);objects.append(ob)
        if K=='ice':
            uv=np.load(R/'cache/ice-uv'/f'{f:04}.npz')['uv'];layer=ob.data.uv_layers.new(name='Advected ice');loop_ids=np.array([z.vertex_index for z in ob.data.loops]);layer.data.foreach_set('uv',uv[loop_ids].ravel())
        if K=='lava':
            # Face materials directly bind the transported enthalpy. This avoids
            # silently missing point-color attributes on the meshed cache.
            ob.data.materials.clear()
            for tm in thermal_mats:ob.data.materials.append(tm)
            faceheat=a['heat'][fa].mean(1);ob.data.polygons.foreach_set('material_index',np.clip((faceheat*64).astype('i4'),0,63))
        at=ob.data.color_attributes.new('thermal','FLOAT_COLOR','POINT');at.data.foreach_set('color',np.column_stack([np.repeat(a['heat'][:,None],3,axis=1),np.ones(len(v))]).astype('f4').ravel());ob.data.update()
        state=np.load(R/'cache'/K/f'{f:04}.npz');pp=state['p'];phase=state['phase'];ids=np.arange(len(pp));rng=np.random.default_rng(419)
        if K=='ice':
            ok=(ids%19==0)&(phase>.5);rad=.0025+.004*((ids[ok]*.717)%1)**3;objects.append(points('Sparse entrapped air',pp[ok],rad,bubble,scale=np.tile([.4,1,1.7],(ok.sum(),1))))
            ok=(phase>.78)&(ids%7==0)&(np.sin(pp[:,0]*7+pp[:,2]*11)>.25);rad=.002+.002*(ids[ok]*.173%1);objects.append(points('Surface freezing patches',pp[ok],rad,frost))
        if K=='lava':
            crustdata=np.load(R/'cache/lava/crust'/f'{f:04}.npz');cp=crustdata['p'];rad=crustdata['r'];rot=crustdata['rotation'];objects.append(points('Advected solid crust fragments',cp,rad,crust,rot,np.tile([1.2,.22,1],(len(cp),1))))
    finish(s,K,f)
