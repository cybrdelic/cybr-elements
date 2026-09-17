"""Field-line, discharge and projection versions of the actual sigil contours."""
import numpy as np
from materials import scene
from motion import smooth
def build(kind):
    colors={'energy':[(.015,.19,1),(1,.24,.008)],'spirit':[(.06,.95,.43),(.32,.08,.65)],'lightning':[(.82,.90,1),(.20,.40,1)],'lightning-redirection':[(.82,.9,1),(.20,.4,1)],'spirit-projection':[(.18,.72,.53),(.06,.28,.21)]}[kind]
    return [scene.emission(kind+str(i),c,24 if 'lightning' in kind else 3) for i,c in enumerate(colors)]
def segments(path,active):
    split=np.flatnonzero(np.diff(np.r_[False,active,False]));return [path[a:b] for a,b in zip(split[::2],split[1::2]) if b-a>1]
def frame(data,t,kind,mats):
    p=data['paths'];birth=data['pathbirth'];offset=data['offsets'];objects=[];rng=np.random.default_rng(713)
    lightning='lightning' in kind
    pulse=1.
    if lightning:
        at=np.arange(.15,11.6,.29);age=t-at;phase=np.abs(age);pulse=float(np.maximum(0,1-phase/.040).max())
        if pulse<=0:return objects
    for group,mat in enumerate(mats):
        paths=[];radii=[]
        mat.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=(24 if lightning else 3)*pulse
        for a,b in zip(offset[:-1],offset[1:]):
            rest=p[a:b];born=birth[a:b];active=born<t
            if not np.any(active):continue
            tangent=np.gradient(rest,axis=0);normal=np.c_[-tangent[:,2],np.zeros(len(rest)),tangent[:,0]];normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-6)
            for strand in range(1 if lightning else 4):
                phase=rest[:,0]*17+rest[:,2]*11+strand*1.57+t*(4 if kind=='energy' else 2)
                amplitude=.004 if lightning else .006+strand*.006
                pos=rest+normal*(amplitude*np.cos(phase+group*np.pi))[:,None];pos[:,1]+=amplitude*np.sin(phase)
                if lightning:
                    pos+=rng.normal(0,.009,pos.shape)
                    if kind=='lightning-redirection' and t<.6:
                        start=np.array([-5.,0,3.9]);target=pos[np.flatnonzero(active)[-1]];u=np.linspace(0,1,120);pos=start*(1-u[:,None])+target*u[:,None]+rng.normal(0,.012,(120,3));active=np.ones(120,dtype=bool)
                release=max(0,t-11)
                if kind=='spirit-projection':pos+=np.array([group*release*.7,group*.2,group*release*.4])
                else:pos+=normal*(release*.025*np.sin(phase))[:,None]
                life=np.exp(-release*(1.5 if kind!='energy' else 1.0));rad=(.0042 if lightning else .0025)*life
                for part in segments(pos,active):paths.append(part);radii.append(rad)
        if paths:objects.append(scene.curve(kind+' material channels',paths,radii,mat))
    return objects
