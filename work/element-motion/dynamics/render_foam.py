import sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from scene import *
from cache_io import fluid_mesh
s=setup(96)
water=material('Water between foam patches',(.94,.98,1),.022,trans=1,ior=1.333)
foam=material('Wet aerated microfoam',(.88,.92,.94),.34,trans=0,ior=1.333);bs=foam.node_tree.nodes.get('Principled BSDF');bs.inputs['Coat Weight'].default_value=.4;bs.inputs['Coat Roughness'].default_value=.06;bs.inputs['Subsurface Weight'].default_value=.05;bs.inputs['Subsurface Radius'].default_value=(.002,.0025,.003)
bubble=material('Larger wet bubble films',(.96,.99,1),.025,trans=1,ior=1.333)
objects=[]
for f in frames():
    for o in objects:remove(o)
    objects=[];v,fa,drop,dr=fluid_mesh(f)
    if len(v):objects.append(mesh('Resolved liquid carrier',v,fa,water,True))
    a=np.load(R/'cache/foam'/f'{f:04}.npz');p=a['p'];rad=a['r'];film=a['film'];ids=a['id'];active=film>.08
    if len(p):
        rot=np.column_stack([ids*.717%6.28,ids*.371%6.28,ids*.921%6.28]);objects.append(points('Advected fine foam',p[active],rad[active],foam,rot[active]))
        hero=active&(rad>.0105);objects.append(points('Resolved larger films',p[hero],rad[hero],bubble,rot[hero]))
    finish(s,'foam',f)
