import sys,math,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from helpers import *
K=sys.argv[sys.argv.index('--kind')+1];s,cam=setup(96);rng=np.random.default_rng(812)
mat=rock_material(gain=.18) if K=='seismic' else material('Vibrating thin graphite membrane',(.07,.09,.10),.23,metal=.7) if K=='sound' else material('Heated iron filament',(.025,.017,.012),.4,metal=.6)
if K=='heat':
 n=mat.node_tree.nodes;l=mat.node_tree.links;p=n.get('Principled BSDF');attr=n.new('ShaderNodeAttribute');attr.attribute_name='Temperature';bb=n.new('ShaderNodeBlackbody');l.new(attr.outputs['Fac'],bb.inputs[0]);l.new(bb.outputs[0],p.inputs['Emission Color']);power=n.new('ShaderNodeMath');power.operation='DIVIDE';power.inputs[1].default_value=1600;l.new(attr.outputs['Fac'],power.inputs[0]);pw=n.new('ShaderNodeMath');pw.operation='POWER';pw.inputs[1].default_value=12;l.new(power.outputs[0],pw.inputs[0]);l.new(pw.outputs[0],p.inputs['Emission Strength']);bloom(s,1.5,-.94)
else:data=np.load(R/f'{K}-waves.npz');hs=data['height']
take=selected();ob=None;dust=None
for f in sorted(take):
 t=f/30;front=np.clip((t-.08)/1.6,0,1);N=max(2,int(front*460));us=np.linspace(0,front,N);vs=[];fa=[];temps=[]
 if ob:
  old=ob.data;bpy.data.objects.remove(ob,do_unlink=True);bpy.data.meshes.remove(old)
 for i,u in enumerate(us):
  p0,d,_,_=pose(.08+1.6*float(u));normal=np.array([-d[1],0,d[0]]);center=np.array([p0[0],0,p0[1]]);age=max(0,t-.08-1.6*u)
  if K=='heat':
   # Convective and radiative cooling of the hot source, with no opacity fade.
   temperature=1700.
   for step in range(int(age*120)):
    temperature-=((temperature-295)*.65+5.67e-8*.8*(temperature**4-295**4)/1600)/120
   width=.037;osc=math.sin(u*50+t*5)*.002*(temperature/1700)**3
  else:
   ix=int(np.clip((p0[0]+4.75)/9.5*(hs.shape[2]-1),0,hs.shape[2]-1));iz=int(np.clip((p0[1]+.35)/4.7*(hs.shape[1]-1),0,hs.shape[1]-1));osc=float(hs[f,iz,ix])*(3 if K=='seismic' else 1.2);width=.24 if K=='seismic' else .17
  for j in range(9):
   w=(j-4)/4;co=center+normal*w*width;co[1]=osc*(1-w*w)+.025*w*w
   if K=='seismic':co[1]+=.018*math.sin(u*98+w*7)*math.sin(u*47-w*5)
   vs.append(co);temps.append(temperature if K=='heat' else 0)
  if i:
   for j in range(8):q=(i-1)*9+j;fa.append((q,q+1,q+10,q+9))
 ob=mesh('Physical '+K+' carrier',vs,fa,mat,True);uv_xz(ob,2);ob.hide_render=front<.005
 sol=ob.modifiers.new('Material section','SOLIDIFY');sol.thickness=.05 if K=='seismic' else .008 if K=='sound' else .004
 if K=='heat':at=ob.data.attributes.new('Temperature','FLOAT','POINT');at.data.foreach_set('value',temps)
 if K in ['sound','seismic']:
  if dust:
   old=dust.data;bpy.data.objects.remove(dust,do_unlink=True);bpy.data.meshes.remove(old)
  base=np.array([[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]]);tri=np.array([[0,2,4],[2,1,4],[1,3,4],[3,0,4],[2,0,5],[1,2,5],[3,1,5],[0,3,5]]);cent=np.array(vs)[::3].copy();cent[:,1]-=.012;rad=.004 if K=='sound' else .009;vv=(cent[:,None]+base[None]*rad).reshape(-1,3);ff=(tri[None]+np.arange(len(cent))[:,None,None]*6).reshape(-1,3);dust=mesh('Fine responding surface grains',vv,ff,material('Fine grain',(.24,.20,.11),.72));dust.hide_render=front<.005
 finish(s,K,f)
(R/f'{K}-mechanism.json').write_text(json.dumps({'background':'RGB 0 black','emitter':'shared-trail.json','mechanism':'radiative and convective cooling of a visible hot source' if K=='heat' else 'integrated elastic wave response on a visible material carrier','frames':120}),encoding='utf-8')
