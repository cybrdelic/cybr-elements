"""Persistent branching channels with brief return strokes and re-strikes.
Procedural electrical VFX; this is not a Maxwell or dielectric breakdown solver.
"""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));sys.path.insert(0,str(R.parent));from scene import *
from shared_motion import pose
K=sys.argv[sys.argv.index('--kind')+1];s=setup(48)
core=emission('Electrical channel',(0.82,.90,1),38);branch=emission('Fainter ionized branches',(.20,.40,1),7);glare(s,1.7,-.89)
rng=np.random.default_rng(619);events=[]
for index,at in enumerate([.18,.39,.64,.86,1.08,1.30,1.51,1.68,2.02,2.47,2.92]):
    start=max(.08,at-.32);end=min(1.68,at)
    if at>1.7:start=.08;end=1.68
    ts=np.linspace(start,end,130);positions=[]
    for t in ts:
        p,d,_,_=pose(float(t));positions.append([p[0],0,p[1]])
    path=np.array(positions);u=np.linspace(0,1,len(path));jitter=np.zeros_like(path)
    for freq,amp in [(5,.10),(13,.048),(31,.018),(67,.006)]:
        phase=rng.uniform(0,6.28,3);jitter+=np.sin(u[:,None]*freq*6.28+phase)*amp
    path+=jitter*np.sin(np.pi*u)[:,None]
    if K=='lightning-redirection':
        if at<.40:
            target=path[-1].copy();uu=np.linspace(0,1,130);path=np.array([-4.9,0,3.8])*(1-uu[:,None])+target*uu[:,None]+jitter*np.sin(np.pi*uu)[:,None]
        elif at>=1.68:
            startp=path[-1].copy();uu=np.linspace(0,1,130);path=startp*(1-uu[:,None])+np.array([5.2,0,3.5])*uu[:,None]+jitter*np.sin(np.pi*uu)[:,None]
    paths=[path];radii=[np.full(len(path),.0034)]
    for j in rng.choice(np.arange(12,115),9,replace=False):
        count=int(rng.integers(9,26));direction=rng.normal(size=3);direction[1]*=.35;direction/=np.linalg.norm(direction);direction*=rng.uniform(.10,.52);uu=np.linspace(0,1,count);fork=path[j]+uu[:,None]*direction
        fork+=rng.normal(0,.017,(count,3))*np.sin(np.pi*uu)[:,None];paths.append(fork);radii.append(.0015*(1-uu)**1.3)
    events.append((at,paths,radii))
objects=[]
for f in frames():
    for o in objects:remove(o)
    objects=[];t=f/30
    for at,paths,rr in events:
        age=t-at
        # Exposure integral across a frame preserves sub-frame flashes.
        weight=0.
        for st,amp,duration in [(0,1,.018),(.043,.58,.012),(.092,.28,.01)]:
            overlap=max(0,min(t+1/30,at+st+duration)-max(t,at+st));weight+=overlap*30*amp
        if weight<=0:continue
        if K=='lightning-redirection':
            # Incoming, guided, and outgoing events were constructed above.
            paths=[p.copy() for p in paths]
        core.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=38*weight
        objects.append(curve('Discharge trunk',[paths[0]],[rr[0]],core));objects.append(curve('Persistent branch hierarchy',paths[1:],rr[1:],branch))
    finish(s,K,f)
(R/f'{K}-mechanism.json').write_text(json.dumps({'frames':frames(),'events':len(events),'model':'procedural persistent channels, subframe exposure, return stroke and restrikes','limits':'Art-directed channel generation; not an electromagnetic solver'},indent=2),encoding='utf-8')
