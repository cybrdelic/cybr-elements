"""Render the reviewed materials on the original CYBRDELIC source silhouettes."""
import sys,time,json,hashlib,shutil
from pathlib import Path
import numpy as np
import bpy
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from motion import *
import materials
from materials import scene
args=sys.argv[sys.argv.index('--')+1:];K=args[args.index('--kind')+1];V=args[args.index('--variant')+1]
selected=list(map(int,args[args.index('--frames')+1].split(','))) if '--frames' in args else list(range(TOTAL))
dependencyNames=['render-balanced.py','materials.py','motion.py','botanical.py','channels.py',f'source-{V}.npz']
configuration=hashlib.sha256(b''.join((R/n).read_bytes() for n in dependencyNames)+(K+V+str('--eevee' in args)+str('--cpu' in args)).encode()).hexdigest()
progressdir=R/'progress';progressdir.mkdir(exist_ok=True);progressfile=progressdir/f'{K}-{V}.json'
prior=json.loads(progressfile.read_text()) if progressfile.exists() else {}
completed=set(prior.get('frames',[])) if prior.get('configuration')==configuration else set()
def record(frame):
    completed.add(frame);tmp=progressfile.with_suffix('.tmp');tmp.write_text(json.dumps({'configuration':configuration,'frames':sorted(completed)}),encoding='utf-8');tmp.replace(progressfile)
data=np.load(R/f'source-{V}.npz');state=materials.build(K);s=state['s'];s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100
s.camera.location.z=2.35;s.cycles.samples=64 if K not in ['sand','snow'] else 112
out=R/'frames'/f'{K}-{V}';out.mkdir(parents=True,exist_ok=True)
if '--eevee' in args or K in ['metal','sand','snow','seismic','plants','healing','energy','spirit','lightning','lightning-redirection','spirit-projection','flight']:
    s.render.engine='BLENDER_EEVEE_NEXT';s.eevee.taa_render_samples=64
    if '--eevee' in args:out=R/'frames'/f'{K}-{V}-eevee';out.mkdir(parents=True,exist_ok=True)
if '--cpu' in args:
    s.render.engine='CYCLES';s.cycles.device='CPU';s.render.threads=4;s.cycles.denoiser='OPENIMAGEDENOISE';s.cycles.denoising_use_gpu=False
rest=data['v'];faces=data['faces'];born=data['born'];groups=data['groups'];rng=np.random.default_rng(740)
if K in ['glass','ice','crystal']:
    fragments=np.load(R.parents[1]/f'element-mark-{V}.npz');rest=fragments['verts'].copy();rest[:,1]*=.83666;faces=fragments['faces'];born=fragments['born'];groups=fragments['groups'];centers=fragments['centers'].copy();centers[:,1]*=.83666
mat=state.get('mat',state.get('mats',[None])[0]);objects=[]
particleKinds=['sand','snow','seismic'];bodyKinds=['metal','ice','glass','crystal','mud','blood','lava','foam']
if K in particleKinds:
    pp=data['particles'];pb=data['particlebirth'];ids=np.arange(len(pp));rad=np.clip(.0048/np.maximum(rng.random(len(pp)),.025)**.42,.0048,.017)
    if K=='snow':rad*=1.25
    mats=state.get('mats',[mat]);tags=ids%len(mats);rotation=rng.uniform(0,6.28,(len(pp),3));shape=rng.uniform(.7,1.3,(len(pp),3))
if K=='lava':
    cidx=np.flatnonzero((rest[:,1]<-.025)&(np.arange(len(rest))%3==0));cr=rest[cidx];cb=born[cidx]
if K in ['foam','ice']:
    pp=data['particles'][::2];pb=data['particlebirth'][::2];ids=np.arange(len(pp));rads=.003+.004*(ids*.717%1)**4
if K in ['plants','healing']:
    import importlib.util
    spec=importlib.util.spec_from_file_location('sigil_botanical',R/'botanical.py');botanical=importlib.util.module_from_spec(spec);spec.loader.exec_module(botanical)
    leaves=botanical.prepare(data,K)
    if K=='healing':repairmat=scene.emission('Localized tissue repair',(.02,.8,.16),5)
if K in ['energy','spirit','lightning','lightning-redirection','spirit-projection']:
    import channels
if K=='flight':
    pp=data['particles'][::8];pb=data['particlebirth'][::8];rad=.0017+.0025*(np.arange(len(pp))*.717%1)**3
    def wake(at):
        pos=pp.copy();phase=pp[:,0]*11+pp[:,2]*14;age=np.maximum(0,at-pb)
        pos[:,0]+=.045*np.cos(phase+age*5);pos[:,2]+=.045*np.sin(phase+age*5);pos[:,1]+=.07*np.sin(phase*.7-age*4)
        release=max(0,at-11);pos[:,0]+=1.8*release+.6*release**2;pos[:,2]+=.14*release*np.sin(phase);pos[:,1]+=.2*release*np.cos(phase)
        return pos
cache={};reused=0
started=time.time()
for f in selected:
    if '--resume' in args and f in completed and (out/f'{f:04}.jpg').exists():continue
    t=f/FPS
    if K in bodyKinds+particleKinds+['plants','healing'] and t>=13.5:
        shutil.copyfile(R/'black-frame.jpg',out/f'{f:04}.jpg')
        record(f)
        continue
    for ob in objects:
        orphanGroups=[m.node_group for m in ob.modifiers if m.type=='NODES' and m.node_group]
        scene.remove(ob)
        for group in orphanGroups:
            if group.users==0:bpy.data.node_groups.remove(group)
    objects=[]
    cx,width=camera(data,t);s.camera.location.x=float(cx);s.camera.data.ortho_scale=float(width)
    if K in bodyKinds:
        active=np.max(born[faces],axis=1)<t
        p=displaced(rest,born,t,K,groups if K in ['glass','ice','crystal'] else None)
        if K in ['glass','ice','crystal'] and t>RELEASE:
            angle=np.sin(groups*.717)*(t-RELEASE)*.8;local=rest-centers[groups];c=np.cos(angle);sn=np.sin(angle);rotated=local.copy();rotated[:,0]=local[:,0]*c-local[:,2]*sn;rotated[:,2]=local[:,0]*sn+local[:,2]*c;p+=rotated-local
        if K=='metal':p[:,1]+=np.sin(rest[:,0]*3+rest[:,2]*4)*.027
        if K=='ice':p[:,1]+=.006*np.sin(rest[:,0]*47+rest[:,2]*31)
        if K=='crystal':p[:,1]+=np.sin(groups*1.733)*.045
        ob=scene.mesh('Material sigil '+V,p,faces[active],state.get('water',mat) if K=='foam' else mat,K!='crystal');objects.append(ob)
        if K=='ice':
            layer=ob.data.uv_layers.new(name='Material coordinates');vi=np.asarray([x.vertex_index for x in ob.data.loops]);uv=np.c_[(rest[:,0]+5.25)/2.2,rest[:,2]/2.2];layer.data.foreach_set('uv',uv[vi].astype('f4').ravel())
        if K=='lava':
            heat=np.clip(1-.016*np.maximum(0,t-born)-.16*np.maximum(0,t-RELEASE),0,1)
            ob.data.materials.clear()
            for m in state['thermal_mats']:ob.data.materials.append(m)
            ob.data.polygons.foreach_set('material_index',np.clip((heat[faces[active]].mean(1)*64).astype('i4'),0,63))
            alive=cb<t-.20;cp=displaced(cr,cb,t,K);rad=.013+.017*(cidx*.173%1)**2
            objects.append(scene.points('Attached basalt crust',cp[alive],rad[alive],state['crust'],scale=np.tile([1.1,.18,1],(alive.sum(),1))))
        if K in ['foam','ice']:
            active=(pb<t-.1)
            if K=='ice':active&=(ids%13==0)&(t<RELEASE)
            fp=displaced(pp,pb,t,K)
            if K=='foam':
                active&=((ids*.373%1)>np.clip((t-RELEASE)*.32,0,1));fp[:,1]-=.035
                m=state['foam'];rr=rads
            else:m=state['bubble'];rr=rads*.5
            objects.append(scene.points('Fine '+K+' inclusions',fp[active],rr[active],m))
    elif K in particleKinds:
        p=displaced(pp,pb,t,K)
        if K=='seismic':p[:,2]+=.025*np.sin(pp[:,0]*14-t*18)*np.exp(-np.maximum(0,t-RELEASE))
        for j,m in enumerate(mats):
            active=(pb<t)&(tags==j);objects.append(scene.points('Material grains',p[active],rad[active],m,rotation[active],shape[active]))
    elif K in ['plants','healing']:
        botanical.frame(leaves,t,K);paths=[];rr=[]
        from channels import segments
        for a,b in zip(data['offsets'][:-1],data['offsets'][1:]):
            p=displaced(data['paths'][a:b],data['pathbirth'][a:b],t,K)
            for part in segments(p,data['pathbirth'][a:b]<t):paths.append(part);rr.append(.012)
        if paths:objects.append(scene.curve('Connected living sigil',paths,rr,mat))
        if K=='healing':
            age=t-data['pathbirth'];active=(age>.4)&(age<1.3);pos=displaced(data['paths'],data['pathbirth'],t,K);objects.append(scene.points('Repair front',pos[active],np.full(active.sum(),.007),repairmat))
    elif K in ['energy','spirit','lightning','lightning-redirection','spirit-projection']:
        objects=channels.frame(data,t,K,state['mats'])
    elif K=='flight':
        p=wake(t);prev=wake(t-1/30);delta=p-prev;length=np.linalg.norm(delta,axis=1);rotation=np.c_[-np.arctan2(delta[:,1],np.sqrt(delta[:,0]**2+delta[:,2]**2)),np.arctan2(delta[:,0],delta[:,2]),np.zeros(len(p))];stretch=1+length/rad*.15;shape=np.c_[1/np.sqrt(stretch),1/np.sqrt(stretch),stretch];active=pb<t
        objects.append(scene.points('Exposed wake pathlines',(p[active]+prev[active])/2,rad[active],mat,rotation[active],shape[active]))
    else:raise ValueError(K)
    s.render.filepath=str(out/f'{f:04}.jpg');s.frame_set(f+1)
    # Reuse only exactly unchanged geometry/material states during a settled hold.
    key=None
    if K in ['metal','glass','crystal','sand','snow'] and 9.6<=t<11:
        key='settled-'+K
    if key in cache:shutil.copyfile(cache[key],s.render.filepath);reused+=1
    else:
        bpy.ops.render.render(write_still=True)
        if key is not None:cache[key]=s.render.filepath
    record(f)
    if f%30==0 or len(selected)<10:print('FRAME',K,V,f,round(time.time()-started,1),flush=True)
(R/f'render-{K}-{V}.json').write_text(json.dumps({'kind':K,'variant':V,'frames':selected,'configuration':configuration,'seconds':time.time()-started,'reusedSettledFrames':reused,'sourceSha256':json.loads((R/f'source-{V}.json').read_text())['sourceSha256'],'method':'Original source geometry, reviewed shader recipes, supported damped motion and gravity release','limits':'Authored bending support; this retargeting pass does not rerun the earlier FLIP/MPM solves'},indent=2),encoding='utf-8')
