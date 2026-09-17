"""Radiatively cooling hot particles make the heat study readable on black."""
from pathlib import Path
import sys,bpy,numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from common import *
s=setup();s.view_settings.exposure=-.6;scene.glare(s,1.2,-.96)
a=np.load(D/'cache/heat/tracers.npz');P=a['p'];T=a['temperature'];birth=a['birth'];rad=a['r'];mats=[]
for i in range(28):
 temperature=650+i*27;mat=scene.material('Cooling solid '+str(temperature)+' K',(.012,.011,.010),.36,metal=.65);n=mat.node_tree.nodes;l=mat.node_tree.links;p=n['Principled BSDF'];bb=n.new('ShaderNodeBlackbody');bb.inputs[0].default_value=temperature;l.new(bb.outputs[0],p.inputs['Emission Color']);p.inputs['Emission Strength'].default_value=4*(temperature/1350)**4*max(0,(temperature-650)/700)**2;mats.append(mat)
objects=[]
for f in selected():
 for ob in objects:scene.remove(ob)
 objects=[];t=(f+1)/30;live=(birth<=t)&(T[f]>680);groups=np.clip(((T[f]-650)/27).astype(int),0,27)
 for i,mat in enumerate(mats):
  ids=np.flatnonzero(live&(groups==i))
  if len(ids):objects.append(instance('Resolved cooling particles '+str(i),P[f,ids],rad[ids]*.45,mat,subdivision=1))
 finish(s,'heat',f)
