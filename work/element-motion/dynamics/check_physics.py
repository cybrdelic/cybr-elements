"""Independent integration check and actual simulated constraint residuals."""
import os
os.environ['OMP_NUM_THREADS']='2'
import sys,json,math
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));import mpm
wp=mpm.wp;wp.set_device('cpu')
coords=np.array([[i,j,k] for i in [-1,0,1] for j in [-1,0,1] for k in [-1,0,1]],dtype='f4')*.035+[-5,-1,.5];N=len(coords);zero=np.zeros((N,3),dtype='f4')
x=wp.array(coords.astype('f4'),dtype=wp.vec3,device='cpu');v=wp.array(zero,dtype=wp.vec3,device='cpu');rest=wp.array(coords.astype('f4'),dtype=wp.vec3,device='cpu')
C=wp.zeros(N,dtype=wp.mat33,device='cpu');F=wp.array(np.tile(np.eye(3,dtype='f4'),(N,1,1)),dtype=wp.mat33,device='cpu');jp=wp.zeros(N,dtype=float,device='cpu');birth=wp.zeros(N,dtype=float,device='cpu');clock=wp.array(np.array([3],dtype='f4'),dtype=float,device='cpu');turn=wp.zeros(482,dtype=float,device='cpu')
shape=(24,24,40);gm=wp.zeros(shape,dtype=float,device='cpu');gv=wp.zeros(shape,dtype=wp.vec3,device='cpu');dx=.1;dt=1/600
for _ in range(120):
    gm.zero_();gv.zero_();wp.launch(mpm.transfer,N,[x,v,C,F,jp,rest,birth,clock,turn,gm,gv,dx,dt,.00004,1000.,0.,0.,2],device='cpu');wp.launch(mpm.grid,shape,[gm,gv,dt,dx,2],device='cpu');wp.launch(mpm.gather,N,[x,v,C,birth,clock,gv,dx,dt],device='cpu');wp.launch(mpm.tick,1,[clock,dt],device='cpu')
actual=x.numpy().mean(0);elapsed=.2;drag=.75;expected_drop=-9.81/drag*(elapsed-(1-math.exp(-drag*elapsed))/drag);error=float(abs(actual[2]-(.5+expected_drop)))
assert error<.004,('gravity/drag integration mismatch',error)
assert np.max(np.abs(actual[:2]-[-5,-1]))<.001
result={'gravityDrag':{'seconds':elapsed,'expectedDrop':expected_drop,'measuredDrop':float(actual[2]-.5),'error':error,'passed':True}}
q=np.load(R/'cache/plants/rods.npz');p=q['p'];edges=q['edges'];length=q['length'];births=q['birth'];residuals=[]
for f in range(120):
    t=(f+1)/30;active=(births[edges].max(1)<t-.1)
    d=np.linalg.norm(p[f,edges[:,0]]-p[f,edges[:,1]],axis=1);residuals.extend(np.abs(d[active]/length[active]-1).tolist())
result['plantConstraints']={'relativeErrorMedian':float(np.median(residuals)),'relativeErrorP95':float(np.quantile(residuals,.95)),'max':float(np.max(residuals))}
assert result['plantConstraints']['relativeErrorP95']<.08
(R/'physics-checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
