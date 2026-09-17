from common import *
import numpy as np

def material(name,color,rough=.5,metal=0,trans=0,ior=1.45):
 m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF')
 for key,value in [('Base Color',(*color,1)),('Roughness',rough),('Metallic',metal),('Transmission Weight',trans),('IOR',ior)]:p.inputs[key].default_value=value
 return m

def rock_material(name='Scanned basalt',gain=.25):
 m=material(name,(.04,.04,.04));n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF');tc=n.new('ShaderNodeTexCoord')
 for suffix,socket in [('diff','Base Color'),('rough','Roughness'),('nor_gl','Normal')]:
  tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(R/'assets'/f'rock_boulder_cracked_{suffix}_2k.jpg'));l.new(tc.outputs['UV'],tex.inputs[0])
  if suffix!='diff':tex.image.colorspace_settings.name='Non-Color'
  if suffix=='diff':
   mix=n.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1;mix.inputs[2].default_value=(gain,gain,gain,1);l.new(tex.outputs[0],mix.inputs[1]);l.new(mix.outputs[0],p.inputs[socket])
  elif suffix=='nor_gl':
   normal=n.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.4;l.new(tex.outputs[0],normal.inputs['Color']);l.new(normal.outputs[0],p.inputs[socket])
  else:l.new(tex.outputs[0],p.inputs[socket])
 return m

def mesh(name,verts,faces,mat,smooth=False):
 me=bpy.data.meshes.new(name);me.from_pydata(np.asarray(verts).tolist(),[],[list(f) for f in faces]);me.materials.append(mat);me.update();ob=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(ob)
 for poly in me.polygons:poly.use_smooth=smooth
 return ob

def uv_xz(ob,scale=1):
 uv=ob.data.uv_layers.new()
 for loop in ob.data.loops:
  p=ob.data.vertices[loop.vertex_index].co;uv.data[loop.index].uv=((p.x+4.8)/9.6*scale,p.z/4.8*scale)

def plane_context(mat=None,y=.55,width=12,height=7,res=2):
 mat=mat or rock_material();xs=np.linspace(-width/2,width/2,res);zs=np.linspace(-.35,-.35+height,max(2,int(res*height/width)));xx,zz=np.meshgrid(xs,zs);v=np.column_stack([xx.ravel(),np.full(xx.size,y),zz.ravel()]);ids=np.arange(xx.size).reshape(xx.shape);fa=np.stack([ids[:-1,:-1],ids[1:,:-1],ids[1:,1:],ids[:-1,1:]],axis=-1).reshape(-1,4);ob=mesh('Physical reference surface',v,fa,mat,True);uv_xz(ob);return ob,v,xx,zz

def emission(name,color,power):
 m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes;n.clear();e=n.new('ShaderNodeEmission');e.inputs[0].default_value=(*color,1);e.inputs[1].default_value=power;o=n.new('ShaderNodeOutputMaterial');m.node_tree.links.new(e.outputs[0],o.inputs[0]);return m,e

def bloom(s,threshold=2,mix=-.85):
 s.use_nodes=True;n=s.node_tree.nodes;n.clear();r=n.new('CompositorNodeRLayers');g=n.new('CompositorNodeGlare');g.glare_type='FOG_GLOW';g.quality='HIGH';g.threshold=threshold;g.size=7;g.mix=mix;c=n.new('CompositorNodeComposite');s.node_tree.links.new(r.outputs['Image'],g.inputs[0]);s.node_tree.links.new(g.outputs[0],c.inputs[0])

def finish(s,kind,f):
 out=R/f'{kind}-frames';out.mkdir(exist_ok=True);s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=96;s.render.filepath=str(out/f'{f:04}.jpg');bpy.ops.render.render(write_still=True)

def selected(default=(20,42,75,105)):
 if '--full' in sys.argv:return set(range(120))
 if '--frame' in sys.argv:return {int(sys.argv[sys.argv.index('--frame')+1])}
 return set(default)

def brandmark():
 import re,xml.etree.ElementTree as ET
 path=R.parents[2]/'outputs/cybrdelic-type/typefaces/vector/CybrdelicSigil-Regular-wordmark.svg';root=ET.parse(path).getroot();contours=[]
 for node in root.iter():
  if not node.tag.endswith('path'):continue
  d=node.attrib['d'];assert not re.search('[CQASTcqast]',d),'Expected the approved polygon master'
  for contour in re.split('[Mm]',d)[1:]:
   values=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',contour)))
   if len(values)>=6:contours.append(np.array(values).reshape(-1,2))
 allv=np.concatenate(contours);center=(allv.min(0)+allv.max(0))/2;scale=7/np.ptp(allv[:,0]);cu=bpy.data.curves.new('Approved Cybrdelic Sigil master','CURVE');cu.dimensions='2D';cu.fill_mode='BOTH';cu.extrude=.048;cu.bevel_depth=.006;cu.bevel_resolution=3;cu.resolution_u=2
 for c in contours:
  points=(c-center)*scale;sp=cu.splines.new('POLY');sp.points.add(len(points)-1);sp.use_cyclic_u=True
  for point,co in zip(sp.points,points):point.co=(float(co[0]),float(-co[1]),0,1)
 ob=bpy.data.objects.new('CYBRDELIC approved wordmark',cu);bpy.context.collection.objects.link(ob);ob.rotation_euler.x=math.pi/2;bpy.context.view_layer.objects.active=ob;ob.select_set(True);bpy.ops.object.convert(target='MESH');ob=bpy.context.object;bpy.ops.object.transform_apply(location=False,rotation=True,scale=True);ob.select_set(False);ob.data.materials.append(material('Solid CYBRDELIC',(.16,.18,.2),.25,metal=.65));v=np.array([list(v.co) for v in ob.data.vertices]);return ob,v
