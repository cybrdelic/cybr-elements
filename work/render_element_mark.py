"""Authored elemental motion: capillary sheet / advected volume / rigid fragments.
Water is a reduced suspended-sheet model, not a FLIP bake.
"""
import bpy,sys,os,math,time,json,shutil
import numpy as np
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).parent
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
element=args[0] if args else 'water';variant=args[1] if len(args)>1 else '01'
pilot='--pilot' in args;testframe=int(args[args.index('--frame')+1]) if '--frame' in args else 240
benchmark='--benchmark' in args
startframe=int(args[args.index('--start-frame')+1]) if '--start-frame' in args else 0
endframe=int(args[args.index('--end-frame')+1]) if '--end-frame' in args else 450
data=np.load(ROOT/f'element-mark-{variant}.npz');motion=np.load(ROOT/f'brand-fire-{variant}.npz')
verts=data['verts'];faces=data['faces'];groups=data['groups'];centers=data['centers'];born=data['born'];gb=data['groupbirth'];rng=np.random.default_rng(870+int(variant))
out=ROOT/f'{element}-brand-{variant}-frames';out.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='BLENDER_EEVEE_NEXT' if element=='air' else 'CYCLES'
if element!='water':
    if hasattr(s.eevee,'taa_render_samples'):s.eevee.taa_render_samples=64
    if hasattr(s.eevee,'volumetric_tile_size'):s.eevee.volumetric_tile_size='4'
    if hasattr(s.eevee,'volumetric_samples'):s.eevee.volumetric_samples=64
s.cycles.samples=64 if element=='water' else 24;s.cycles.use_denoising=True;s.cycles.use_adaptive_sampling=True;s.cycles.adaptive_threshold=.035 if element=='water' else .08;s.cycles.adaptive_min_samples=16 if element=='water' else 8
s.cycles.device='GPU';s.cycles.denoiser='OPTIX';s.cycles.denoising_use_gpu=True
s.cycles.max_bounces=12;s.cycles.transmission_bounces=10;s.cycles.volume_bounces=2
if element=='water':
    s.cycles.use_auto_tile=True
    s.cycles.caustics_reflective=False;s.cycles.caustics_refractive=False
s.render.threads_mode='FIXED';s.render.threads=4;s.render.use_persistent_data=True
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for dev in prefs.devices:dev.use=dev.type=='OPTIX'
s.render.resolution_x=3840 if element=='water' else 2560;s.render.resolution_y=2160 if element=='water' else 1440;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.color_depth='8';s.render.image_settings.compression=30
s.view_settings.view_transform='AgX';s.render.fps=30
world=bpy.data.worlds.new('Reflection studio');s.world=world;world.use_nodes=True
wn=world.node_tree.nodes;wl=world.node_tree.links;bg=wn.get('Background');bg.inputs['Color'].default_value=(.22,.27,.33,1);bg.inputs['Strength'].default_value=.45
lp=wn.new('ShaderNodeLightPath');black=wn.new('ShaderNodeBackground');black.inputs[0].default_value=(.0001,.0002,.0003,1)
mix=wn.new('ShaderNodeMixShader');ray=wn.new('ShaderNodeMath');ray.operation='MAXIMUM';wl.new(lp.outputs['Is Camera Ray'],ray.inputs[0]);wl.new(lp.outputs['Is Transmission Ray'],ray.inputs[1]);wl.new(ray.outputs[0],mix.inputs[0]);wl.new(bg.outputs[0],mix.inputs[1]);wl.new(black.outputs[0],mix.inputs[2]);wl.new(mix.outputs[0],wn.get('World Output').inputs[0])
def area(name,loc,power,color,width,height):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.color=color;d.shape='RECTANGLE';d.size=width;d.size_y=height
    o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,2))-o.location).to_track_quat('-Z','Y').to_euler()
area('Long silver reflection',(-3,-4,5),2200,(.78,.90,1),7,.75)
area('White edge',(4,-2.5,3),1600,(.9,.95,1),.65,6)
area('Back scatter',(-1,2.8,4.5),3300,(.38,.70,1) if element!='earth' else (1,.65,.32),6,2)
area('Low warm bounce',(1,-4,.4),450,(1,.74,.42),5,1)
if element=='earth':
    for light in bpy.data.lights:light.energy*=.24
bpy.ops.object.camera_add(location=(0,-18,2.6));cam=bpy.context.object;s.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=11.4
def material(name,color,rough):
    mat=bpy.data.materials.new(name);mat.use_nodes=True;p=mat.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;return mat
floor=material('Near black wet stage',(.003,.005,.008),.20 if element=='water' else .8)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-1.35));bpy.context.object.data.materials.append(floor);bpy.context.object.visible_camera=False
liquid=material('Clear water / IOR 1.333',(.65,.88,.98),.024);nn=liquid.node_tree.nodes;ll=liquid.node_tree.links;p=nn.get('Principled BSDF');p.inputs['IOR'].default_value=1.333;p.inputs['Transmission Weight'].default_value=1
absorb=nn.new('ShaderNodeVolumeAbsorption');absorb.inputs['Color'].default_value=(.19,.62,.79,1);absorb.inputs['Density'].default_value=.48;ll.new(absorb.outputs[0],nn.get('Material Output').inputs['Volume'])
noise=nn.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=75;noise.inputs['Detail'].default_value=3
bump=nn.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.035;bump.inputs['Distance'].default_value=.002;ll.new(noise.outputs['Fac'],bump.inputs['Height']);ll.new(bump.outputs['Normal'],p.inputs['Normal'])
surface=liquid.copy() if element=='water' else material('Fractured earth',(.16,.082,.032),.87)
sn=surface.node_tree.nodes;sl=surface.node_tree.links;sp=sn.get('Principled BSDF')
if element=='earth':
    rock=sn.new('ShaderNodeTexNoise');rock.inputs['Scale'].default_value=7;rock.inputs['Detail'].default_value=5;rock.inputs['Roughness'].default_value=.8
    ramp=sn.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.22;ramp.color_ramp.elements[0].color=(.025,.011,.006,1);ramp.color_ramp.elements[1].position=.8;ramp.color_ramp.elements[1].color=(.34,.20,.085,1)
    sl.new(rock.outputs['Fac'],ramp.inputs[0]);sl.new(ramp.outputs[0],sp.inputs['Base Color'])
    grain=sn.new('ShaderNodeTexNoise');grain.inputs['Scale'].default_value=105;grain.inputs['Detail'].default_value=2
    tex=sn.new('ShaderNodeTexCoord');sl.new(tex.outputs['Object'],rock.inputs['Vector']);sl.new(tex.outputs['Object'],grain.inputs['Vector'])
    bump=sn.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.7;bump.inputs['Distance'].default_value=.055;sl.new(grain.outputs['Fac'],bump.inputs['Height']);sl.new(bump.outputs[0],sp.inputs['Normal'])
def mesh_object(name,v,f,mat):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(v,[],f);mesh.update();o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o);o.data.materials.append(mat)
    for poly in mesh.polygons:poly.use_smooth=True
    return o
body=None
if element!='air':
    body=mesh_object('Liquid sheet' if element=='water' else 'Earth fragments',verts,faces,surface)
    attr=body.data.attributes.new('arrival','FLOAT','POINT');attr.data.foreach_set('value',born)
    a=sn.new('ShaderNodeAttribute');a.attribute_name='arrival';clock=sn.new('ShaderNodeValue');clock.name='Arrival clock'
    sub=sn.new('ShaderNodeMath');sub.operation='SUBTRACT';sl.new(clock.outputs[0],sub.inputs[0]);sl.new(a.outputs['Fac'],sub.inputs[1])
    grow=sn.new('ShaderNodeMapRange');grow.clamp=True;grow.interpolation_type='SMOOTHSTEP';grow.inputs['From Min'].default_value=-.03;grow.inputs['From Max'].default_value=.18;sl.new(sub.outputs[0],grow.inputs[0])
    transparent=sn.new('ShaderNodeBsdfTransparent');mix=sn.new('ShaderNodeMixShader');sl.new(grow.outputs[0],mix.inputs[0]);sl.new(transparent.outputs[0],mix.inputs[1]);sl.new(sp.outputs[0],mix.inputs[2]);sl.new(mix.outputs[0],sn.get('Material Output').inputs['Surface'])
def vapor():
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,3));o=bpy.context.object;o.name='Advected air volume';o.scale=(16,2.4,8);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    mat=bpy.data.materials.new('Silver wind / scattering');mat.use_nodes=True;n=mat.node_tree.nodes;l=mat.node_tree.links;n.clear();output=n.new('ShaderNodeOutputMaterial');vol=n.new('ShaderNodeVolumePrincipled');vol.inputs['Color'].default_value=(.70,.83,.96,1);vol.inputs['Anisotropy'].default_value=.35;l.new(vol.outputs[0],output.inputs['Volume'])
    def mathnode(op,a=None,b=None):
        nd=n.new('ShaderNodeMath');nd.operation=op
        for i,x in enumerate([a,b]):
            if x is None:continue
            if isinstance(x,(int,float)):nd.inputs[i].default_value=x
            else:l.new(x,nd.inputs[i])
        return nd.outputs[0]
    tc=n.new('ShaderNodeTexCoord');sep=n.new('ShaderNodeSeparateXYZ');l.new(tc.outputs['Generated'],sep.inputs[0])
    u=mathnode('MULTIPLY_ADD',sep.outputs['X'],16/10.5);u.node.inputs[2].default_value=(-8+5.25)/10.5
    v=mathnode('MULTIPLY_ADD',sep.outputs['Z'],8/5.8);v.node.inputs[2].default_value=-1/5.8
    uv=n.new('ShaderNodeCombineXYZ');l.new(u,uv.inputs[0]);l.new(v,uv.inputs[1])
    timevalue=n.new('ShaderNodeValue');timevalue.name='Air time'
    texture=n.new('ShaderNodeTexNoise');texture.noise_dimensions='4D';texture.inputs['Scale'].default_value=9;texture.inputs['Detail'].default_value=3;texture.inputs['Roughness'].default_value=.7;l.new(timevalue.outputs[0],texture.inputs['W'])
    stretch=n.new('ShaderNodeVectorMath');stretch.operation='MULTIPLY';stretch.inputs[1].default_value=(1,3,7);l.new(tc.outputs['Generated'],stretch.inputs[0]);l.new(stretch.outputs[0],texture.inputs['Vector'])
    warp=n.new('ShaderNodeVectorMath');warp.operation='SUBTRACT';l.new(texture.outputs['Color'],warp.inputs[0]);warp.inputs[1].default_value=(.5,.5,.5)
    amp=n.new('ShaderNodeVectorMath');amp.operation='SCALE';amp.inputs[3].default_value=.055;l.new(warp.outputs[0],amp.inputs[0])
    add=n.new('ShaderNodeVectorMath');add.operation='ADD';l.new(uv.outputs[0],add.inputs[0]);l.new(amp.outputs[0],add.inputs[1])
    image=n.new('ShaderNodeTexImage');image.image=bpy.data.images.load(str(ROOT/f'element-mask-{variant}.png'));image.image.colorspace_settings.name='Non-Color';image.extension='CLIP';l.new(add.outputs[0],image.inputs[0])
    birth=n.new('ShaderNodeTexImage');birth.image=bpy.data.images.load(str(ROOT/f'element-arrival-{variant}.png'));birth.image.colorspace_settings.name='Non-Color';birth.extension='CLIP';l.new(uv.outputs[0],birth.inputs[0])
    clock=n.new('ShaderNodeValue');clock.name='Air birth';age=mathnode('SUBTRACT',clock.outputs[0],birth.outputs['Color']);active=mathnode('MULTIPLY',age,80);active.node.use_clamp=True
    depth=mathnode('SUBTRACT',sep.outputs['Y'],.5);depth=mathnode('MULTIPLY',depth,depth);depth=mathnode('MULTIPLY',depth,-55);depth=mathnode('EXPONENT',depth)
    detail=mathnode('SUBTRACT',texture.outputs['Fac'],.48);detail=mathnode('MULTIPLY',detail,6);detail.node.use_clamp=True
    den=mathnode('MULTIPLY',image.outputs['Color'],detail);den=mathnode('MULTIPLY',den,depth);den=mathnode('MULTIPLY',den,active)
    density=n.new('ShaderNodeValue');density.name='Air mass';density.outputs[0].default_value=.35;den=mathnode('MULTIPLY',den,density.outputs[0]);l.new(den,vol.inputs['Density'])
    o.data.materials.append(mat);return o,mat,amp
def advected_vapor():
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,3));o=bpy.context.object;o.name='Advected tracer volume';o.scale=(16,2.4,8);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    mat=bpy.data.materials.new('Advected air density');mat.use_nodes=True;n=mat.node_tree.nodes;l=mat.node_tree.links;n.clear()
    output=n.new('ShaderNodeOutputMaterial');vol=n.new('ShaderNodeVolumePrincipled');vol.inputs['Color'].default_value=(.7,.84,.98,1);vol.inputs['Anisotropy'].default_value=.25;l.new(vol.outputs[0],output.inputs['Volume'])
    tc=n.new('ShaderNodeTexCoord');sep=n.new('ShaderNodeSeparateXYZ');l.new(tc.outputs['Generated'],sep.inputs[0]);uv=n.new('ShaderNodeCombineXYZ')
    for axis,factor,offset in [(0,16/10.5,(-8+5.25)/10.5),(1,8/5.8,-1/5.8)]:
        m=n.new('ShaderNodeMath');m.operation='MULTIPLY_ADD';m.inputs[1].default_value=factor;m.inputs[2].default_value=offset;l.new(sep.outputs['X' if axis==0 else 'Z'],m.inputs[0]);l.new(m.outputs[0],uv.inputs[axis])
    tex=n.new('ShaderNodeTexImage');tex.name='Advected field';tex.image=bpy.data.images.load(str(ROOT/f'air-density-{variant}/0000.png'));tex.image.colorspace_settings.name='Non-Color';tex.extension='CLIP';l.new(uv.outputs[0],tex.inputs[0])
    dep=n.new('ShaderNodeMath');dep.operation='SUBTRACT';dep.inputs[1].default_value=.5;l.new(sep.outputs['Y'],dep.inputs[0]);sq=n.new('ShaderNodeMath');sq.operation='MULTIPLY';l.new(dep.outputs[0],sq.inputs[0]);l.new(dep.outputs[0],sq.inputs[1]);factor=n.new('ShaderNodeMath');factor.operation='MULTIPLY';factor.inputs[1].default_value=-55;l.new(sq.outputs[0],factor.inputs[0]);exp=n.new('ShaderNodeMath');exp.operation='EXPONENT';l.new(factor.outputs[0],exp.inputs[0]);mul=n.new('ShaderNodeMath');mul.operation='MULTIPLY';l.new(exp.outputs[0],mul.inputs[0]);l.new(tex.outputs['Color'],mul.inputs[1]);gain=n.new('ShaderNodeMath');gain.operation='MULTIPLY';gain.inputs[1].default_value=.7;l.new(mul.outputs[0],gain.inputs[0]);l.new(gain.outputs[0],vol.inputs['Density']);o.data.materials.append(mat)
    return o,mat,None
air=None
if element=='air':air,airmat,airwarp=advected_vapor()
# Individually moving satellite droplets / grit with real geometry.
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1 if element=='earth' else 2,radius=1);ico=bpy.context.object;base=np.array([v.co[:] for v in ico.data.vertices]);tri=np.array([p.vertices[:] for p in ico.data.polygons]);bpy.data.objects.remove(ico,do_unlink=True)
if element=='earth':base*=rng.uniform(.65,1.25,(len(base),1))*np.array([.7,1.2,.85])
count=1000 if element=='water' else (3200 if element=='earth' else 800)
bt=rng.uniform(.15,6.7,count);qx=np.interp(bt*1.875,motion['times'],motion['points'][:,0]);qz=np.interp(bt*1.875,motion['times'],motion['points'][:,1]);anchors=np.c_[qx,rng.normal(0,.09,count),qz]
pv=rng.normal(0,.6,(count,3));pv[:,2]+=rng.uniform(.2,1.1,count)
radii=rng.uniform(.007,.025,count) if element!='earth' else rng.uniform(.006,.026,count)
pf=(tri[None,:,:]+np.arange(count)[:,None,None]*len(base)).reshape(-1,3)
pmat=liquid if element=='water' else (surface if element=='earth' else material('Air motes',(.6,.77,.85),.3))
particles=mesh_object('Satellite droplets' if element=='water' else 'Grit' if element=='earth' else 'Air motes',np.tile(base,(count,1)),pf,pmat)
if element=='air':particles.hide_render=True
if element=='earth':
    # Grit has no per-vertex arrival shader; it uses the same stone texture.
    pmat=surface.copy();pn=pmat.node_tree.nodes;pl=pmat.node_tree.links;pl.new(pn.get('Principled BSDF').outputs[0],pn.get('Material Output').inputs['Surface']);particles.data.materials.clear();particles.data.materials.append(pmat)
velocity=rng.normal(0,1.0,(420,3));velocity[:,2]=rng.uniform(.4,1.5,420)
phase=rng.uniform(0,math.tau,420);local=verts-centers[groups]
jet=None
if element=='water':
    rings=140;sides=40;angles=np.arange(sides)*math.tau/sides
    jf=[(i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j) for i in range(rings-1) for j in range(sides)]
    jet=mesh_object('Travelling liquid front',np.zeros((rings*sides,3)),jf,liquid)
started=time.monotonic()
empty=False
def update(t):
    global empty
    if body:
        sn.get('Arrival clock').outputs[0].default_value=t
        age=np.maximum(0,t-gb);release=np.maximum(0,t-11-.1*np.sin(phase))
        if element=='water':
            new=verts.copy()
            # Dispersive capillary ripples across the suspended liquid sheet.
            for k,amp in [(5,.035),(12,.012),(28,.003)]:
                omega=math.sqrt(9.81*k+.074/1000*k**3)
                new[:,1]+=amp*np.sin(verts[:,0]*k+verts[:,2]*k*.61-t*omega)
            rel=release[groups];amount=1-np.exp(-rel*4)
            # Surface tension contracts released patches; each then falls freely.
            length=np.linalg.norm(local,axis=1).clip(.001);rad=.080+.025*np.sin(phase[groups])
            sphere=local/length[:,None]*rad[:,None]
            new+=(sphere-local)*amount[:,None]
            new+=velocity[groups]*rel[:,None]*.40;new[:,2]-=4.905*rel**2
        else:
            settle=np.exp(-age*5.5)*np.cos(age*8.0)
            shift=np.c_[np.sin(phase)*settle*.6,np.cos(phase)*settle*.4,-settle*2.0]
            shift+=velocity*release[:,None]*.6;shift[:,2]-=4.905*release**2
            theta=release*(phase-math.pi)*1.2+settle*.08*np.sin(phase)
            loc=local.copy();c=np.cos(theta[groups]);ss=np.sin(theta[groups]);loc[:,0]=local[:,0]*c+local[:,2]*ss;loc[:,2]=local[:,2]*c-local[:,0]*ss
            new=centers[groups]+loc*.935+shift[groups]
        body.data.vertices.foreach_set('co',new.astype('f').ravel());body.data.update()
    if air:
        image=airmat.node_tree.nodes.get('Advected field').image;image.filepath=str(ROOT/f'air-density-{variant}/{round(t*30):04}.png');image.reload()
    if jet:
        jet.hide_render=t>8.4 or t<.06
        qt=np.linspace(max(0,t-.48),t,rings);pt=qt*1.875-.08
        path=np.c_[np.interp(pt,motion['times'],motion['points'][:,0]),np.zeros(rings),np.interp(pt,motion['times'],motion['points'][:,1])]
        end=np.maximum(0,qt-6.87);path[:,0]+=end*1.5;path[:,2]-=end**2*4.9
        tangent=np.gradient(path,axis=0);tangent/=np.linalg.norm(tangent,axis=1)[:,None].clip(.0001)
        side=np.cross(tangent,np.tile([0,1,0],(rings,1)));side/=np.linalg.norm(side,axis=1)[:,None].clip(.0001);up=np.cross(tangent,side)
        r=.13*np.sin(np.linspace(.03,math.pi-.03,rings))**.5*(1+.12*np.sin(qt*45-t*12))
        jv=path[:,None,:]+r[:,None,None]*(np.cos(angles)[None,:,None]*side[:,None,:]+np.sin(angles)[None,:,None]*up[:,None,:])
        jet.data.vertices.foreach_set('co',jv.astype('f').ravel());jet.data.update()
    age=t-bt;positive=np.maximum(age,0)
    if element=='air':
        p=anchors+pv*positive[:,None]*.22;p[:,0]+=positive**1.2*.15;p[:,2]+=positive*.1
    else:
        p=anchors+pv*positive[:,None];p[:,2]-=2.5*positive**2
    p[age<0,2]=-20
    if element=='earth':p[:,2]=np.where(p[:,2]<-1.3,-1.3,p[:,2])
    coords=(p[:,None,:]+base[None,:,:]*radii[:,None,None]).reshape(-1,3)
    particles.data.vertices.foreach_set('co',coords.astype('f').ravel());particles.data.update()
    zoom=np.clip((t-5.55)/1.9,0,1);zoom=zoom*zoom*(3-2*zoom)
    follow=np.mean(np.interp(np.clip(t*1.875+np.linspace(-1.2,.35,18)-.08,0,motion['times'][-1]),motion['times'],motion['points'][:,0]))*(1-zoom)
    cam.location=(follow,-18,2.65);cam.rotation_euler=(Vector((follow,0,2.35))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=6.4+5*zoom
    empty=False
    if element!='air' and t>11:
        bottom=2.35-cam.data.ortho_scale*9/32
        empty=max(float(np.max(new[:,2]+new[:,1]/60)),float(np.max(p[:,2]+p[:,1]/60)))<bottom-.12
empty_frame=None
for frame in (range(240,243) if benchmark else [testframe] if pilot else range(startframe,endframe)):
    update(frame/30);s.render.filepath=str(out/f'{frame:04}.png')
    if empty and empty_frame:
        shutil.copy2(empty_frame,s.render.filepath)
    else:
        bpy.ops.render.render(write_still=True)
        if empty:empty_frame=s.render.filepath
    print('ELEMENT_PROGRESS '+json.dumps({'element':element,'variant':variant,'frame':frame,'elapsed':round(time.monotonic()-started,2)}),flush=True)
(ROOT/f'{element}-brand-{variant}-report.json').write_text(json.dumps({'element':element,'variant':variant,'resolution':[s.render.resolution_x,s.render.resolution_y],'samples':64 if element=='air' else s.cycles.samples,'triangles':len(faces),'frames':3 if benchmark else 1 if pilot else 450,'elapsed':time.monotonic()-started,'model':'capillary sheet and ballistic droplets' if element=='water' else '2D advected condensation density with diffusion and evaporation, rendered as a heterogeneous volume' if element=='air' else 'suspended stone fragments with gravity release'},indent=2))
