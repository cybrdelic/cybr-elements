"""Shared black-stage render contract. No backdrop geometry or floor."""
import bpy, sys, math
from pathlib import Path
import numpy as np
from mathutils import Vector
R=Path(__file__).resolve().parent
ASSETS=R.parent/'realism/assets'

def setup(samples=64):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=samples
    s.cycles.use_denoising=True;s.cycles.denoiser='OPTIX';s.cycles.adaptive_threshold=.018
    s.cycles.max_bounces=16;s.cycles.transmission_bounces=12;s.cycles.glossy_bounces=8;s.cycles.diffuse_bounces=2
    s.render.threads_mode='FIXED';s.render.threads=3;s.render.use_persistent_data=True
    s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100
    s.render.image_settings.file_format='JPEG';s.render.image_settings.quality=97;s.render.fps=30
    s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast'
    pref=bpy.context.preferences.addons['cycles'].preferences;pref.compute_device_type='OPTIX';pref.get_devices()
    for d in pref.devices:d.use=d.type=='OPTIX'
    w=bpy.data.worlds.new('Pitch black');w.use_nodes=True;w.node_tree.nodes['Background'].inputs[0].default_value=(0,0,0,1);w.node_tree.nodes['Background'].inputs[1].default_value=0;s.world=w
    for name,loc,power,width,height,col in [
        ('Broad neutral key',(-2,-4,5),1600,5.0,1.8,(1,.94,.84)),
        ('Cool narrow rim',(2,1.6,3.8),1900,1.4,4.0,(.78,.89,1)),
        ('Low strip',(-1,-1.5,-.1),500,4,.3,(1,1,1))]:
        d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='RECTANGLE';d.size=width;d.size_y=height;d.color=col
        ob=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector((0,0,1.9))-ob.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add(location=(0,-15,1.903125));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1.903125))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=10.5;s.camera=cam
    return s

def material(name,color,rough=.4,metal=0,trans=0,ior=1.45):
    m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF')
    for key,value in [('Base Color',(*color,1)),('Roughness',rough),('Metallic',metal),('Transmission Weight',trans),('IOR',ior)]:p.inputs[key].default_value=value
    return m

def emission(name,color,power=1):
    m=material(name,color);p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Emission Color'].default_value=(*color,1);p.inputs['Emission Strength'].default_value=power
    return m

def mesh(name,v,f,mat,smooth=False):
    me=bpy.data.meshes.new(name);me.from_pydata(np.asarray(v).tolist(),[],np.asarray(f).tolist());me.materials.append(mat);me.update();ob=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(ob)
    if smooth:me.polygons.foreach_set('use_smooth',np.ones(len(me.polygons),dtype=bool))
    return ob

def remove(ob):
    me=ob.data;bpy.data.objects.remove(ob,do_unlink=True)
    if me.users==0:
        if isinstance(me,bpy.types.Mesh):bpy.data.meshes.remove(me)
        elif isinstance(me,bpy.types.Curve):bpy.data.curves.remove(me)

def points(name,p,r,mat,rotation=None,scale=None):
    p=np.asarray(p);n=len(p)
    ob=mesh(name,p,np.empty((0,3),dtype=int),mat)
    attr=ob.data.attributes.new('grain_scale','FLOAT_VECTOR','POINT')
    scales=np.broadcast_to(np.asarray(r).reshape(-1,1),(n,3)).copy()
    if scale is not None:scales*=scale
    attr.data.foreach_set('vector',scales.astype('f4').ravel())
    attr=ob.data.attributes.new('grain_rotation','FLOAT_VECTOR','POINT');attr.data.foreach_set('vector',(np.zeros((n,3)) if rotation is None else rotation).astype('f4').ravel())
    mod=ob.modifiers.new('Instanced physical detail','NODES');g=bpy.data.node_groups.new(name+' instances','GeometryNodeTree');mod.node_group=g
    g.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');g.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    nd=g.nodes;ln=g.links;inp=nd.new('NodeGroupInput');out=nd.new('NodeGroupOutput');ico=nd.new('GeometryNodeMeshIcoSphere');ico.inputs['Radius'].default_value=1;ico.inputs[' subdivisions' if ' subdivisions' in ico.inputs else 'Subdivisions'].default_value=1
    sm=nd.new('GeometryNodeSetMaterial');sm.inputs['Material'].default_value=mat;ln.new(ico.outputs['Mesh'],sm.inputs['Geometry'])
    inst=nd.new('GeometryNodeInstanceOnPoints');ln.new(inp.outputs['Geometry'],inst.inputs['Points']);ln.new(sm.outputs['Geometry'],inst.inputs['Instance'])
    for name0,socket in [('grain_scale','Scale'),('grain_rotation','Rotation')]:
        at=nd.new('GeometryNodeInputNamedAttribute');at.data_type='FLOAT_VECTOR';at.inputs['Name'].default_value=name0;ln.new(at.outputs['Attribute'],inst.inputs[socket])
    ln.new(inst.outputs['Instances'],out.inputs['Geometry']);return ob

def curve(name,paths,radii,mat):
    cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.resolution_u=1;cu.bevel_resolution=2;cu.bevel_depth=1
    for k,path in enumerate(paths):
        if len(path)<2:continue
        sp=cu.splines.new('POLY');sp.points.add(len(path)-1);sp.points.foreach_set('co',np.column_stack([path,np.ones(len(path))]).astype('f4').ravel())
        rr=np.broadcast_to(radii[k],(len(path),));sp.points.foreach_set('radius',np.asarray(rr,dtype='f4'))
    ob=bpy.data.objects.new(name,cu);bpy.context.collection.objects.link(ob);cu.materials.append(mat);return ob

def glare(s,threshold=3,mix=-.94):
    s.use_nodes=True;n=s.node_tree.nodes;n.clear();a=n.new('CompositorNodeRLayers');g=n.new('CompositorNodeGlare');g.glare_type='FOG_GLOW';g.quality='HIGH';g.threshold=threshold;g.mix=mix;g.size=7;o=n.new('CompositorNodeComposite');s.node_tree.links.new(a.outputs['Image'],g.inputs[0]);s.node_tree.links.new(g.outputs[0],o.inputs[0])

def frames():
    if '--frames' in sys.argv:return [int(x) for x in sys.argv[sys.argv.index('--frames')+1].split(',')]
    return list(range(120)) if '--full' in sys.argv else [30,45,65,90]

def finish(s,kind,frame):
    d=R/'frames'/kind;d.mkdir(parents=True,exist_ok=True);s.render.filepath=str(d/f'{frame:04}.jpg');s.frame_set(frame+1);bpy.ops.render.render(write_still=True);print('FRAME',kind,frame,flush=True)
