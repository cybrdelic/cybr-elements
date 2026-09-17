import sys,math
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from helpers import *
K=sys.argv[sys.argv.index('--kind')+1];s,cam=setup(96);cache=np.load(R/f'{K}-sim.npz');positions=cache['positions'];radii=cache['radii'];rng=np.random.default_rng(199);N=len(radii)
if K in ['pressure','flight']:pass
else:
 bpy.ops.mesh.primitive_plane_add(size=100);floor=bpy.context.object;floor.visible_camera=False;floor.data.materials.append(material('Dark contact ground',(.006,.007,.009),.68))
if K=='sand':
 colors=[(.19,.105,.042),(.12,.060,.022),(.28,.20,.11),(.08,.064,.05),(.38,.31,.19)];mats=[material('Quartz and feldspar grains',c,.63) for c in colors]
elif K=='snow':
 mats=[material('Porous ice aggregates',(.8,.88,.94),.56,trans=.12,ior=1.31)];p=mats[0].node_tree.nodes.get('Principled BSDF');p.inputs['Subsurface Weight'].default_value=.28;p.inputs['Subsurface Radius'].default_value=(.018,.024,.03)
else:mats=[material('Entrained fine mineral',(.36,.32,.22),.68)]
base=np.array([[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]]);tri=np.array([[0,2,4],[2,1,4],[1,3,4],[3,0,4],[2,0,5],[1,2,5],[3,1,5],[0,3,5]])
if K=='snow':
 # Fine dendrites form irregular porous aggregates.
 radii*=.6
 vv=[];ff=[]
 for arm in range(6):
  a=arm*math.tau/6;d=np.array([math.cos(a),0,math.sin(a)]);no=np.array([-d[2],0,d[0]])
  segments=[(np.zeros(3),d)]
  for along in [.38,.64]:
   for sign in [-1,1]:segments.append((d*along,d*(along+.20)+no*sign*.22))
  for p0,p1 in segments:
   side=np.cross(p1-p0,[0,1,0]);side=side/np.linalg.norm(side)*.045;o=len(vv);vv.extend([p0-side,p0+side,p1+side,p1-side,p0+[0,.035,0],p1+[0,.035,0]]);ff.extend([(o,o+1,o+4),(o+1,o+2,o+5,o+4),(o+2,o+3,o+5),(o+3,o,o+4,o+5)])
 base0=np.array(vv);f0=list(ff);vv=[];ff=[]
 for cluster in range(3):
  rot0=np.linalg.qr(rng.normal(size=(3,3)))[0];offset=len(vv);vv.extend(base0@rot0*.7+rng.normal(0,.20,3));ff.extend([tuple(np.array(face)+offset) for face in f0])
 base=np.array(vv);faces=[tuple(np.array(f)+i*len(base)) for i in range(N) for f in ff]
else:faces=(tri[None]+np.arange(N)[:,None,None]*len(base)).reshape(-1,3)
rot=np.linalg.qr(rng.normal(size=(N,3,3)))[0];shape=np.einsum('vi,nij->nvj',base,rot)*rng.uniform(.7,1.25,(N,1,3));ob=mesh('Material particles',(positions[0,:,None]+shape*radii[:,None,None]).reshape(-1,3),faces,mats[0])
for mat in mats[1:]:ob.data.materials.append(mat)
if K=='sand':
 ids=rng.integers(0,len(mats),N)
 for p in ob.data.polygons:p.material_index=int(ids[p.index//8])
for f in sorted(selected()):
 sh=shape.copy()
 if K=='snow':
  angle=np.sin(f/30*3+np.arange(N)*2.4)*.45;ca=np.cos(angle);sa=np.sin(angle);x=sh[:,:,0].copy();sh[:,:,0]=x*ca[:,None]-sh[:,:,1]*sa[:,None];sh[:,:,1]=x*sa[:,None]+sh[:,:,1]*ca[:,None]
 verts=positions[f,:,None]+sh*radii[:,None,None];ob.data.vertices.foreach_set('co',verts.ravel());ob.data.update();finish(s,K,f)
