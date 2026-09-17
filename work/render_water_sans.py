"""Suspended slender liquid jets: moving source, inertial nodes, axial tension,
viscous damping, volume-preserving cross sections and gravity release.
This is a reduced liquid-jet model, not the original FLIP water solver.
"""
import bpy, numpy as np, math, sys, os, json, time
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import sans_motion as font
pilot='--pilot' in sys.argv
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=24;s.cycles.use_denoising=True
s.render.engine='CYCLES';s.cycles.use_adaptive_sampling=False;s.cycles.adaptive_threshold=.08;s.cycles.adaptive_min_samples=4;s.render.use_persistent_data=True
s.cycles.device='GPU';s.cycles.denoiser='OPTIX';s.cycles.denoising_use_gpu=True;s.render.threads_mode='FIXED';s.render.threads=6
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX';prefs.get_devices()
for dev in prefs.devices:dev.use=dev.type=='OPTIX'
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=67 if pilot else 100
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB'
s.render.film_transparent=False
s.view_settings.view_transform='AgX'
world=bpy.data.worlds.new('Studio reflections');s.world=world;world.use_nodes=True
nodes=world.node_tree.nodes;links=world.node_tree.links;bg=nodes.get('Background');bg.inputs['Color'].default_value=(.10,.17,.24,1);bg.inputs['Strength'].default_value=.4
# Off-camera softboxes provide long specular highlights in genuinely refractive water.
def area(name,loc,power,color,size,scale):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.color=color;data.shape='RECTANGLE';data.size=size;data.size_y=scale
    obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj);obj.location=loc;obj.rotation_euler=(Vector((0,0,1.6))-obj.location).to_track_quat('-Z','Y').to_euler()
area('Broad silver key',(-2,-3,5.5),1900,(.76,.88,1),8,2)
area('Cyan rim',(1,1.4,3.5),2500,(.25,.72,1),8,1)
area('Warm narrow edge',(4,-1,2.5),1000,(1,.85,.7),1,4)
mat=bpy.data.materials.new('Water — IOR 1.333');mat.use_nodes=True;mat.use_raytrace_refraction=True;mat.refraction_depth=.17
n=mat.node_tree.nodes;p=n.get('Principled BSDF');p.inputs['Base Color'].default_value=(.55,.86,.96,1);p.inputs['Roughness'].default_value=.065;p.inputs['IOR'].default_value=1.333;p.inputs['Transmission Weight'].default_value=1
absorb=n.new('ShaderNodeVolumeAbsorption');absorb.inputs['Color'].default_value=(.08,.53,.72,1);absorb.inputs['Density'].default_value=.8
mat.node_tree.links.new(absorb.outputs[0],n.get('Material Output').inputs['Volume'])
floor=bpy.data.materials.new('Obsidian stage');floor.diffuse_color=(.008,.015,.021,1);floor.use_nodes=True
floor.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.006,.012,.018,1)
floor.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.25
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.40));bpy.context.object.data.materials.append(floor)
# Dark world to camera, retained studio environment for reflected/refracted rays.
lightpath=nodes.new('ShaderNodeLightPath');mix=nodes.new('ShaderNodeMixShader');black=nodes.new('ShaderNodeBackground');black.inputs[0].default_value=(.001,.003,.006,1)
links.new(lightpath.outputs['Is Camera Ray'],mix.inputs[0]);links.new(bg.outputs[0],mix.inputs[1]);links.new(black.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],nodes.get('World Output').inputs[0])
bpy.ops.object.camera_add(location=(0,-18,4));camera=bpy.context.object;s.camera=camera;camera.data.type='ORTHO';camera.data.lens=50
mesh=bpy.data.meshes.new('Evolving liquid surface');obj=bpy.data.objects.new('Water jets',mesh);bpy.context.collection.objects.link(obj);obj.data.materials.append(mat)
# Each stroke has its own fluid segment; all are emitted sequentially by one nozzle.
groups=[];now=font.START;total=sum(font.lengths);draw=12.93-.1*(len(font.curves)-1)
for curve,length in zip(font.curves,font.lengths):
    dist=np.r_[0,np.cumsum(np.linalg.norm(np.diff(curve,axis=0),axis=1))]
    count=max(4,int(length/.024));q=np.linspace(0,length,count)
    anchor=np.c_[np.interp(q,dist,curve[:,0]),np.zeros(count),np.interp(q,dist,curve[:,1])]
    tangent=np.gradient(anchor,axis=0);tangent/=np.maximum(np.linalg.norm(tangent,axis=1)[:,None],1e-8)
    born=(now+q/total*draw)/1.875
    groups.append(dict(a=anchor,p=anchor.copy(),v=tangent*.45,born=born,rest=length/(count-1),broken=np.zeros(count-1,dtype=bool),phase=np.linspace(0,length,count)*25))
    now+=length/total*draw+.1
angles=np.arange(16)*math.tau/16
started=time.monotonic();out=ROOT/('water-pilot-frames' if pilot else 'water-sans-frames');out.mkdir(exist_ok=True)
def simulate(t,dt):
    for g in groups:
        active=g['born']<=t;n=int(active.sum())
        if n<2:continue
        pos=g['p'][:n];v=g['v'][:n];a=g['a'][:n]
        # Authored suspension acts as an external force. It releases completely at 11 s.
        hold=(t < 11+.18*np.sin(g['phase'][:n]*.6))[:,None].astype(float)
        force=(a-pos)*95*hold-v*(7*hold+.025)
        force[:,2]-=9.81*(1-hold[:,0])
        delta=pos[1:]-pos[:-1];length=np.linalg.norm(delta,axis=1);normal=delta/np.maximum(length[:,None],1e-8)
        g['broken'][:n-1]|=(length>g['rest']*2.8)&(t>10.8)
        tension=normal*((length-g['rest'])*150*(~g['broken'][:n-1]))[:,None]
        force[:-1]+=tension;force[1:]-=tension
        # Longitudinal viscous momentum exchange and capillary perturbations.
        force[1:-1]+=(v[:-2]+v[2:]-2*v[1:-1])*1.8
        force[:,1]+=.8*np.sin(g['phase'][:n]-t*8)*hold[:,0]
        v+=force*dt;pos+=v*dt
        hit=pos[:,2]<-.31
        pos[hit,2]=-.31;v[hit,2]=abs(v[hit,2])*.16;v[hit,:2]*=.93
        g['p'][:n]=pos;g['v'][:n]=v

def surface(t):
    verts=[];faces=[]
    for gi,g in enumerate(groups):
        n=int((g['born']<=t).sum())
        if n<2:continue
        pos=g['p'][:n];v=g['v'][:n];tangent=np.gradient(pos,axis=0);stretch=np.linalg.norm(tangent,axis=1)/g['rest'];tangent/=np.maximum(np.linalg.norm(tangent,axis=1)[:,None],1e-8)
        side=np.cross(tangent,np.tile([0,1,0],(n,1)));side/=np.maximum(np.linalg.norm(side,axis=1)[:,None],1e-8);up=np.cross(tangent,side)
        # Cross-section contracts as a jet stretches, maintaining segment volume.
        radius=.085/np.sqrt(np.maximum(.45,stretch))
        radius*=1+.16*np.sin(g['phase'][:n]-t*7)+.045*np.sin(g['phase'][:n]*2.3+t*12)
        radius*=1+.5*np.exp(-np.maximum(0,t-g['born'][:n])/.16)
        radius[:2]*=[.30,.85];radius[-2:]*=[.85,.30]
        rings=pos[:,None,:]+radius[:,None,None]*(side[:,None,:]*np.cos(angles)[None,:,None]+up[:,None,:]*np.sin(angles)[None,:,None])
        base=len(verts);verts.extend(rings.reshape(-1,3).tolist())
        for j in range(n-1):
            if g['broken'][j]:
                faces.append(tuple(base+j*16+k for k in range(16)))
                faces.append(tuple(base+(j+1)*16+k for k in reversed(range(16))))
            else:
                for k in range(16):faces.append((base+j*16+k,base+j*16+(k+1)%16,base+(j+1)*16+(k+1)%16,base+(j+1)*16+k))
        faces.append(tuple(base+k for k in reversed(range(16))));faces.append(tuple(base+(n-1)*16+k for k in range(16)))
    for j in range(86):
        born=.15+j*.079;age=t-born
        if age<0:continue
        center,direction,on,speed=font.pose(born*1.875)
        if on<.5:continue
        initial=np.array([center[0],0.,center[1]])
        velocity=np.array([-direction[0]*.75+.30*math.sin(j*7),.45*math.sin(j*4),-direction[1]*.75+.6])
        center=initial+velocity*age+np.array([0,0,-1.8])*age*age
        radius=.022+.009*(.5+.5*math.sin(j*13))
        squash=1.
        if center[2]<-.36: center[2]=-.365;squash=.18;radius*=2.0
        base=len(verts)
        for lat in range(9):
            phi=math.pi*(lat+.001)/8.002
            for k in range(12):
                theta=k*math.tau/12
                verts.append((center+radius*np.array([math.sin(phi)*math.cos(theta),math.sin(phi)*math.sin(theta),math.cos(phi)*squash])).tolist())
        for lat in range(8):
            for k in range(12):faces.append((base+lat*12+k,base+lat*12+(k+1)%12,base+(lat+1)*12+(k+1)%12,base+(lat+1)*12+k))
    old=obj.data;new=bpy.data.meshes.new('Liquid frame');new.from_pydata(verts,[],faces);new.materials.append(mat);obj.data=new;bpy.data.meshes.remove(old)
    for p in new.polygons:p.use_smooth=True
    return len(verts)
frames=[240] if '--test' in sys.argv else ([60,240,345] if pilot else range(450))
last=0
for frame in frames:
    t=frame/30
    while last<t-1e-8:simulate(last,1/120);last+=1/120
    count=surface(t)
    zoom=np.clip((t-5.55)/1.9,0,1);zoom=zoom*zoom*(3-2*zoom)
    follow=font.pose(t*1.875-.4)[0][0]*(1-zoom)
    camera.location=(follow,-18,3.7);target=Vector((follow,0,1.65));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=6.4+5*zoom
    s.render.filepath=str(out/f'{frame:04}.png');bpy.ops.render.render(write_still=True)
    print('WATER_PROGRESS '+json.dumps({'frame':frame,'vertices':count,'seconds':round(time.monotonic()-started,1)}),flush=True)
print('WATER_COMPLETE',flush=True)


