import sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from scene import *
if '--kind' in sys.argv and sys.argv[sys.argv.index('--kind')+1]=='seismic':
    exec(compile((R/'seismic.py').read_text(encoding='utf-8'),str(R/'seismic.py'),'exec'))
    raise SystemExit(0)
if '--kind' in sys.argv and sys.argv[sys.argv.index('--kind')+1]=='heat':
    import subprocess
    p=subprocess.run(['C:/Users/alexf/AppData/Local/Programs/Python/Python312/python.exe',str(R/'thermal_optics.py'),*sys.argv[sys.argv.index('--')+1:]])
    raise SystemExit(p.returncode)
if '--kind' in sys.argv and sys.argv[sys.argv.index('--kind')+1] in ['sound','pressure']:
    import subprocess
    p=subprocess.run(['C:/Users/alexf/AppData/Local/Programs/Python/Python312/python.exe',str(R/'acoustic_optics.py'),*sys.argv[sys.argv.index('--')+1:]])
    raise SystemExit(p.returncode)
sys.path.insert(0,str(R.parent));from shared_motion import pose
K=sys.argv[sys.argv.index('--kind')+1];s=setup(64);a=np.load(R/'cache'/K/'tracers.npz');P=a['p'];E=a['energy'];rad=a['r'];tag=a['tag'];N=len(rad)
colors={'flight':[(.38,.47,.51)],'pressure':[(.66,.55,.34)],'sound':[(.75,.77,.70)],'seismic':[(.20,.13,.065)],'heat':[(1,.14,.004)],'energy':[(.015,.19,1),(1,.24,.008)],'spirit':[(.06,.95,.43),(.32,.08,.65)]}[K]
mats=[material(K+str(i),c,.5 if K=='seismic' else .26,metal=.3 if K=='sound' else 0) for i,c in enumerate(colors)]
if K=='heat':
    mats=[]
    for j in range(16):
        temperature=650+j*50;mat=material('Thermal radiation '+str(temperature),(.02,.012,.006),.4);n=mat.node_tree.nodes;l=mat.node_tree.links;bs=n.get('Principled BSDF');bb=n.new('ShaderNodeBlackbody');bb.inputs[0].default_value=temperature;l.new(bb.outputs[0],bs.inputs['Emission Color']);bs.inputs['Emission Strength'].default_value=7*(temperature/1350)**4*np.clip((temperature-650)/700,0,1)**3;mats.append(mat)
    glare(s,2,-.94)
if K in ['energy','spirit']:
    for mat,c in zip(mats,colors):
        bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Emission Color'].default_value=(*c,1);bs.inputs['Emission Strength'].default_value=4
    glare(s,2,-.94)
rot=np.random.default_rng(137).uniform(0,6.28,(N,3));objects=[]
for f in frames():
    for ob in objects:remove(ob)
    objects=[];active=(E[f]>.03)&(P[f,:,2]>-3)
    if K in ['energy','spirit']:active&=(np.arange(N)%37==0)
    if K=='sound':active&=(E[f]>.70)
    if K=='seismic':active&=(np.arange(N)%13==0)
    if K=='flight':
        ids=np.flatnonzero(active&(E[max(0,f-1)]>.03)&(np.arange(N)%3==0));paths=[P[max(0,f-1):f+1,i] for i in ids];radii=[rad[i]*.55*np.sqrt(E[f,i]) for i in ids]
        objects.append(curve('Wake pathlines during one frame',paths,radii,mats[0]))
        active[:]=False
    for j,mat in enumerate(mats):
        groups=np.clip(((a['temperature'][f]-650)/50).astype(int),0,15) if K=='heat' else tag
        ok=active if len(mats)==1 else active&(groups==j)
        radius=rad[ok] if K=='heat' else rad[ok]*np.sqrt(E[f,ok])*(2.5 if K=='seismic' else 1)
        objects.append(points('Transported '+K,P[f,ok],radius,mat,rot[ok],np.tile([1,1,1.3],(ok.sum(),1))))
    if K in ['energy','spirit']:
        # Connected field-line carriers share the trajectory while retaining
        # organized topology and a traveling luminous front.
        t=(f+1)/30;end=min(t,1.68)
        if end>.09:
            ts=np.linspace(.08,end,500);centers=[];normals=[]
            for u in ts:
                q,d,_,_=pose(float(u));centers.append([q[0],0,q[1]]);normals.append([-d[1],0,d[0]])
            centers=np.array(centers);normals=np.array(normals);age=np.maximum(0,t-ts);decay=np.exp(-np.maximum(0,age-1.2)*1.5)
            for group,mat in enumerate(mats):
                paths=[];rr=[]
                for strand in range(12):
                    phase=ts*(24 if K=='energy' else 15)+strand*.52+group*np.pi-age*5
                    width=(.025+strand*.005)*(1 if K=='energy' else .25+.75*np.exp(-age*1.7))
                    path=centers+normals*(np.cos(phase)*width)[:,None]+np.array([0,1,0])[None]*(np.sin(phase)*width)[:,None]
                    pulse=.30+.70*np.exp(-((age%.45)/.11)**2)
                    paths.append(path);rr.append((.0012+.0004*(strand%3))*decay*pulse)
                objects.append(curve('Connected '+K+' channels',paths,rr,mat))
    finish(s,K,f)
