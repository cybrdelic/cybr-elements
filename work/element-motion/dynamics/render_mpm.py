import sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from scene import *
K=sys.argv[sys.argv.index('--kind')+1];s=setup(80)
static=np.load(R/'cache'/K/'static.npz');birth=static['birth'];N=len(birth);rng=np.random.default_rng(91)
colors={'sand':[(.32,.20,.085),(.19,.12,.047),(.42,.31,.16),(.10,.07,.035)],'snow':[(.81,.89,.93)],'metal':[(.53,.57,.61)],'mud':[(.028,.016,.008)]}[K]
mats=[material(K+str(i),c,.52 if K=='sand' else .36 if K=='snow' else .21 if K=='metal' else .33,metal=1 if K=='metal' else 0) for i,c in enumerate(colors)]
if K=='snow':
    p=mats[0].node_tree.nodes.get('Principled BSDF');p.inputs['Subsurface Weight'].default_value=.05;p.inputs['Subsurface Radius'].default_value=(.008,.01,.012);p.inputs['Coat Weight'].default_value=.1
    for light in bpy.data.lights:light.energy*=.42
    s.cycles.use_denoising=False;s.cycles.samples=112
if K=='metal':
    mat=mats[0];nd=mat.node_tree.nodes;ln=mat.node_tree.links;bs=nd.get('Principled BSDF');bs.inputs['Roughness'].default_value=.27;bs.inputs['Anisotropic'].default_value=.5
    tc=nd.new('ShaderNodeTexCoord');scale=nd.new('ShaderNodeVectorMath');scale.operation='MULTIPLY';scale.inputs[1].default_value=(900,12,120);ln.new(tc.outputs['Generated'],scale.inputs[0]);no=nd.new('ShaderNodeTexNoise');no.inputs['Scale'].default_value=1;no.inputs['Detail'].default_value=2;ln.new(scale.outputs[0],no.inputs[0]);bump=nd.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.00012;bump.inputs['Strength'].default_value=.22;ln.new(no.outputs['Fac'],bump.inputs['Height']);ln.new(bump.outputs[0],bs.inputs['Normal'])
radii=np.clip(.0045/np.maximum(rng.random(N),.025)**.40,.0045,.016)
if K=='snow':radii*=1.65
if K=='metal':radii[:]=.012
rot=rng.uniform(0,6.28,(N,3));shape=rng.uniform(.7,1.25,(N,3));ids=rng.integers(0,len(mats),N)
objects=[]
for f in frames():
    for o in objects:remove(o)
    objects=[];a=np.load(R/'cache'/K/f'{f:04}.npz');p=a['p'];active=birth<=float(a['t'])
    if K in ['sand','snow']:
        for j,mat in enumerate(mats):
            ok=active&(ids==j);objects.append(points('Resolved '+K,p[ok],radii[ok],mat,rot[ok],shape[ok]))
        secondary=R/'cache'/K/'secondary'/f'{f:04}.npz'
        if secondary.exists():
            fine=np.load(secondary);objects.append(points('Released material fines',fine['p'],fine['r'],mats[0]))
    else:
        surf=np.load(R/'surface'/K/f'{f:04}.npz');objects.append(mesh('Deformed '+K,surf['v'],surf['f'],mats[0],True))
    finish(s,K,f)
