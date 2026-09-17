import sys,math,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from common import *
s,cam=setup()
with bpy.data.libraries.load(str(R/'assets/nettle_plant_2k.blend'),link=False) as (a,b):b.objects=[name for name in a.objects if name.endswith('LOD0')]
source=[o for o in b.objects if o.type=='MESH']
for image in bpy.data.images:
 target=R/'assets/textures'/Path(image.filepath).name
 if target.exists():image.filepath=str(target);image.reload()
stem=bpy.data.materials.new('Living woody stem');stem.use_nodes=True;bs=stem.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.045,.06,.017,1);bs.inputs['Roughness'].default_value=.65
no=stem.node_tree.nodes.new('ShaderNodeTexNoise');no.inputs['Scale'].default_value=80;no.inputs['Detail'].default_value=4;bu=stem.node_tree.nodes.new('ShaderNodeBump');bu.inputs['Distance'].default_value=.0008;stem.node_tree.links.new(no.outputs['Fac'],bu.inputs['Height']);stem.node_tree.links.new(bu.outputs[0],bs.inputs['Normal'])
rng=np.random.default_rng(217);shoots=[]
for i,u in enumerate(np.linspace(.025,.965,28)):
 u=float(np.clip(u+rng.uniform(-.013,.013),0,1));src=source[i%len(source)];ob=src.copy();ob.data=src.data.copy();ob.animation_data_clear();ob.location=(0,0,0);ob.rotation_euler=(0,0,0);ob.scale=(1,1,1);bpy.context.collection.objects.link(ob);v=np.array([list(v.co) for v in ob.data.vertices]);h=v[:,2].max();scale=rng.uniform(3.8,5.4);p,d,_,_=pose(.08+1.6*u);c=np.array([p[0],0,p[1]]);normal=np.array([-d[1],0,d[0]]);angle=rng.uniform(-.65,.65)+(math.pi if i%2 else 0);direction=normal*math.cos(angle)+np.array([0,1,0])*math.sin(angle);direction=(direction+np.array([d[0],0,d[1]])*.32+np.array([0,0,.4]));direction/=np.linalg.norm(direction);side=np.cross(direction,[0,1,0]);side/=np.linalg.norm(side);depth=np.cross(direction,side);shoots.append((ob,v,h,scale,c,direction,side,depth,u))
objects=[];frames=range(120) if '--full' in sys.argv else [20,42,75]
if '--frame' in sys.argv:frames=[int(sys.argv[sys.argv.index('--frame')+1])]
out=R/'plants-frames';out.mkdir(exist_ok=True)
for f in frames:
 t=f/30;front=np.clip((t-.08)/1.6,0,1)
 for o in objects:
  d=o.data;bpy.data.objects.remove(o,do_unlink=True);bpy.data.curves.remove(d)
 objects=[]
 if front>.005:
  for strand in range(2):
   pts=[]
   for u in np.linspace(0,front,300):
    p,d,_,_=pose(.08+1.6*float(u));pts.append([p[0]+.018*math.sin(u*25+strand*3),.015*math.cos(u*25+strand*3),p[1]])
   objects.append(curve('Growing stem',pts,.017 if strand==0 else .009,stem))
 for ob,v,h,scale,c,direction,side,depth,u in shoots:
  age=t-(.08+1.6*u);g=float(np.clip(age/.9,0,1));ob.hide_render=g<.005
  if ob.hide_render:continue
  z=np.maximum(0,v[:,2]);unfurl=np.clip((g-z/h)*4+.4,0,1);unfurl=unfurl*unfurl*(3-2*unfurl);axial=np.minimum(z,h*g);sway=.018*np.sin(t*3+u*20)*(z/h)**2;vv=c+axial[:,None]*direction*scale+(v[:,0]*unfurl*scale)[:,None]*side+(v[:,1]*unfurl*scale+sway)[:,None]*depth;vv+=((axial/h)**2*.025*scale)[:,None]*np.array([0,0,-1]);ob.data.vertices.foreach_set('co',vv.ravel());ob.data.update()
 s.render.filepath=str(out/f'{f:04}.png');bpy.ops.render.render(write_still=True);print('FRAME',f,flush=True)
(R/'plants-report.json').write_text(json.dumps({'asset':'Poly Haven nettle_plant CC0','shoots':len(shoots),'sharedTrail':True,'samples':s.cycles.samples,'frames':list(frames)}))
