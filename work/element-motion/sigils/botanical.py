"""Attach the same scanned foliage to the original lettering's source paths."""
import numpy as np
import bpy
from materials import scene
from motion import displaced,smooth
def prepare(data,kind):
    with bpy.data.libraries.load(str(scene.ASSETS/'nettle_plant_2k.blend'),link=False) as (a,b):b.objects=[n for n in a.objects if n.endswith('LOD0')]
    sources=[o for o in b.objects if o.type=='MESH']
    for im in bpy.data.images:
        p=scene.ASSETS/'textures'/__import__('pathlib').Path(im.filepath).name
        if p.exists():im.filepath=str(p);im.reload()
    rng=np.random.default_rng(861);chosen=np.linspace(10,len(data['paths'])-10,42).astype(int);result=[]
    for i,index in enumerate(chosen):
        src=sources[i%len(sources)];ob=src.copy();ob.data=src.data.copy();ob.animation_data_clear();ob.location=(0,0,0);ob.rotation_euler=(0,0,0);ob.scale=(1,1,1);bpy.context.collection.objects.link(ob)
        local=np.asarray([v.co[:] for v in ob.data.vertices]);height=max(local[:,2].max(),.01);u=np.clip(local[:,2]/height,0,1);angle=rng.uniform(-1.6,1.6);direction=np.array([np.sin(angle),rng.uniform(-.12,.12),np.cos(angle)])
        root=data['paths'][index];birth=data['pathbirth'][index];length=rng.uniform(.20,.43);side=np.cross(direction,[0,1,0]);side/=np.linalg.norm(side)
        rest=root+u[:,None]*length*direction+local[:,0,None]/height*length*side+local[:,1,None]/height*length*np.array([0,1,0])
        result.append((ob,rest,np.full(len(rest),birth),u,float(birth),root))
    return result
def frame(leaves,t,kind):
    for ob,rest,born,u,birth,root in leaves:
        ob.hide_render=t<birth+.04
        if ob.hide_render:continue
        unfurl=smooth((t-birth-u*.32)/.32);p=root+(rest-root)*unfurl[:,None];p=displaced(p,born,t,kind)
        if kind=='healing':
            gap=np.exp(-((u-.5)/.15)**2);repair=smooth((t-birth-.55)/.7);p[:,0]+=gap*.035*(1-repair)*np.sign(rest[:,0]-root[0])
        ob.data.vertices.foreach_set('co',p.astype('f4').ravel());ob.data.update()
