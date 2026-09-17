import sys,math
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from helpers import *
K=sys.argv[sys.argv.index('--kind')+1];s,cam=setup(96);data=np.load(R/f'{K}-waves.npz');hs=data['height'];xx,zz=np.meshgrid(data['x'],data['z']);v=np.column_stack([xx.ravel(),np.full(xx.size,.40),zz.ravel()]);idx=np.arange(xx.size).reshape(xx.shape);faces=np.stack([idx[:-1,:-1],idx[1:,:-1],idx[1:,1:],idx[:-1,1:]],-1).reshape(-1,4)
if K=='sound':
 m=material('Tensioned brushed bronze membrane',(.028,.033,.038),.24,metal=.95);p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Anisotropic'].default_value=.65
else:m=rock_material(gain=.008 if K=='seismic' else .025)
ob=mesh('Responding physical substrate',v,faces,m,True);uv_xz(ob)
if K=='heat':
 # Render a stable photographed reference for the optical density integration.
 finish(s,'heat-background',0)
else:
 rng=np.random.default_rng(213);N=1700;gx=rng.integers(3,xx.shape[1]-3,N);gz=rng.integers(3,xx.shape[0]-3,N);rad=rng.uniform(.004,.012,N);base=np.array([[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]]);fa=np.array([[0,2,4],[2,1,4],[1,3,4],[3,0,4],[2,0,5],[1,2,5],[3,1,5],[0,3,5]]);points=np.column_stack([xx[gz,gx],np.full(N,.38),zz[gz,gx]]);grain=mesh('Fine surface witness grains',(points[:,None]+base[None]*rad[:,None,None]).reshape(-1,3),(fa[None]+np.arange(N)[:,None,None]*6).reshape(-1,3),material('Fine mineral dust',(.21,.18,.13),.75))
 for f in sorted(selected()):
  h=hs[f];vv=v.copy();vv[:,1]-=h.ravel()*(2 if K=='seismic' else .7);ob.data.vertices.foreach_set('co',vv.ravel());ob.data.update();points[:,1]=.385-h[gz,gx]*(2 if K=='seismic' else .7)-np.abs(h[gz,gx])*.25;grain.data.vertices.foreach_set('co',(points[:,None]+base[None]*rad[:,None,None]).ravel());grain.data.update();finish(s,K,f)
