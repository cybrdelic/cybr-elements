"""Restrained optical corrections to the stronger mud and blood carriers."""
import sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from scene import *
from cache_io import fluid_mesh
K=sys.argv[sys.argv.index('--kind')+1];s=setup(96)
mat=material(K,(.033,.019,.009) if K=='mud' else (.16,.0015,.003),.43 if K=='mud' else .16,trans=.03 if K=='mud' else .24,ior=1.36)
p=mat.node_tree.nodes.get('Principled BSDF');p.inputs['Coat Weight'].default_value=.32;p.inputs['Coat Roughness'].default_value=.10
n=mat.node_tree.nodes;l=mat.node_tree.links
if K=='mud':
    no=n.new('ShaderNodeTexNoise');no.inputs['Scale'].default_value=160;no.inputs['Detail'].default_value=3;bu=n.new('ShaderNodeBump');bu.inputs['Distance'].default_value=.0015;bu.inputs['Strength'].default_value=.4;l.new(no.outputs['Fac'],bu.inputs['Height']);l.new(bu.outputs[0],p.inputs['Normal'])
else:
    ab=n.new('ShaderNodeVolumeAbsorption');ab.inputs['Color'].default_value=(.48,.002,.006,1);ab.inputs['Density'].default_value=11;l.new(ab.outputs[0],n.get('Material Output').inputs['Volume'])
objects=[]
for f in frames():
    for ob in objects:remove(ob)
    objects=[];v,fa,dp,dr=fluid_mesh(f,K=='mud')
    if len(v):objects.append(mesh('Retained '+K+' FLIP carrier',v,fa,mat,True))
    if len(dp):objects.append(points('Resolved liquid breakup',dp,np.minimum(dr,.045),mat))
    finish(s,K,f)
