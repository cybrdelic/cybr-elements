"""Coherent point representation of the original sigil, separating in motion."""
import sys,re,xml.etree.ElementTree as ET,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));sys.path.insert(0,str(R.parent));from scene import *
from shared_motion import pose
s=setup(64);glare(s,2,-.94)
src=R.parents[2]/'outputs/cybrdelic-type/typefaces/vector/CybrdelicSigil-Regular-wordmark.svg';root=ET.parse(src).getroot();pts=[]
for node in root.iter():
    if not node.tag.endswith('path'):continue
    for co in re.split('[Mm]',node.attrib['d'])[1:]:
        vv=np.array(list(map(float,re.findall(r'-?\d+(?:\.\d+)?',co)))).reshape(-1,2)
        if len(vv)<3:continue
        for a,b in zip(vv,np.roll(vv,-1,axis=0)):
            n=max(2,int(np.linalg.norm(a-b)/1.3));pts.extend(np.linspace(a,b,n,endpoint=False))
pts=np.array(pts);pts=(pts-(pts.min(0)+pts.max(0))/2)/(np.ptp(pts[:,0]));base=np.column_stack([pts[:,0],np.zeros(len(pts)),-pts[:,1]])*1.8
rng=np.random.default_rng(524);base=np.repeat(base,2,axis=0)+rng.normal(0,.002,(len(base)*2,3));N=len(base);rad=rng.uniform(.0014,.0034,N)
material0=emission('Source identity',(.008,.18,.15),1.5);material1=emission('Projected identity',(.045,.62,.47),3.0);objects=[]
for f in frames():
    t=f/30
    for ob in objects:remove(ob)
    objects=[];p,d,_,_=pose(min(t,1.68));progress=np.clip((t-.08)/1.6,0,1);release=np.exp(-max(0,t-2)*1.6)
    source=np.array([-3.58,0,1.1]);destination=np.array([p[0],-.1,p[1]])
    if t>.08:
        objects.append(points('Persistent source sigil',base+source,rad*.65*release,material0))
        # Separation preserves every point's location within the original mark.
        ghost=base+destination;ghost[:,1]+=.035*np.sin(base[:,0]*12+t*4)*np.sin(progress*np.pi)
        objects.append(points('Coherent separated sigil',ghost,rad*release,material1))
    finish(s,'spirit-projection',f)
(R/'projection-mechanism.json').write_text(json.dumps({'source':str(src),'points':N,'identityPreserved':True,'mechanism':'coherent separation of sampled original sigil','limits':'Designed fictional projection; emission extinction is an authored energy envelope'},indent=2),encoding='utf-8')
