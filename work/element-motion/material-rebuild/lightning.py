"""Jagged multiscale discharge channels with a persistent branching hierarchy."""
from pathlib import Path
import sys,numpy as np,bpy
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));sys.path.insert(0,str(R.parent))
from common import *
from shared_motion import pose
K=sys.argv[sys.argv.index('--kind')+1] if '--kind' in sys.argv else 'lightning'
s=setup();s.view_settings.exposure=-.7
core=scene.emission('White return-stroke core',(.78,.86,1),100);branchmat=scene.emission('Ionized branching channels',(.29,.48,1),34);corona=scene.emission('Fine violet corona',(.20,.18,1),9);scene.glare(s,1.2,-.78)
rng=np.random.default_rng(81091)

def jagged(anchor,amplitude,depth=4):
 q=np.asarray(anchor).copy()
 for level in range(depth):
  delta=q[1:]-q[:-1];length=np.linalg.norm(delta,axis=1);mid=(q[1:]+q[:-1])*.5
  offset=rng.normal(size=mid.shape);offset[:,1]*=.22;dot=(offset*delta).sum(1)/np.maximum(length**2,1e-9);offset-=delta*dot[:,None]
  offset/=np.maximum(np.linalg.norm(offset,axis=1)[:,None],1e-8);mid+=offset*(length*amplitude*rng.uniform(.45,1.2,len(mid)))[:,None]
  out=np.empty((len(q)*2-1,3));out[::2]=q;out[1::2]=mid;q=out
 return q

events=[]
for at in [.16,.35,.54,.73,.94,1.12,1.32,1.51,1.68,1.91,2.16,2.48,2.83]:
 ts=np.linspace(.08 if at>1.7 else max(.08,at-.37),min(at,1.68),32)
 path=np.array([[pose(float(t))[0][0],0,pose(float(t))[0][1]] for t in ts])
 if K=='lightning-redirection':
  if at<.4:path=np.linspace([-5,0,4.7],path[-1],24)
  elif at>=1.7:path=np.linspace(path[-1],[5.2,0,4],24)
 path=jagged(path,.34,4);trunks=[path];radii=[np.full(len(path),.0048)];forks=[];fr=[];fine=[];finer=[]
 for idx in rng.choice(np.arange(12,len(path)-12),min(34,len(path)-24),replace=False):
  p=path[idx];tangent=path[min(idx+4,len(path)-1)]-path[max(idx-4,0)];tangent/=max(np.linalg.norm(tangent),1e-8)
  direction=tangent*.25+rng.normal(size=3)*[1,.12,1];direction/=np.linalg.norm(direction);length=rng.uniform(.12,.82)*rng.uniform(.7,1)
  q=jagged(np.array([p,p+direction*length]),.26,5);u=np.linspace(0,1,len(q));forks.append(q);fr.append(.0022*(1-u)**.7+.00014)
  for j in rng.choice(np.arange(5,len(q)-3),3,replace=False):
   dd=direction+rng.normal(size=3)*[.65,.08,.65];dd/=np.linalg.norm(dd);z=jagged(np.array([q[j],q[j]+dd*length*rng.uniform(.2,.5)]),.32,4);fine.append(z);finer.append(.0008*(1-np.linspace(0,1,len(z)))+.00007)
 events.append((at,trunks,radii,forks,fr,fine,finer))
objects=[]
for f in selected():
 for ob in objects:scene.remove(ob)
 objects=[];t=f/30
 for at,trunks,rr,forks,fr,fine,finer in events:
  leader_start=at-.028;leader_overlap=max(0,min(t+1/30,at)-max(t,leader_start))
  if leader_overlap>0:
   progress=np.clip((t+1/30-leader_start)/.028,0,1);count=max(2,int(len(trunks[0])*progress));leader=scene.emission('Faint advancing leader '+str(at),(.17,.22,1),2.8*leader_overlap*30)
   objects.append(scene.curve('Advancing leader', [trunks[0][:count]],[rr[0][:count]*.40],leader))
  weight=0
  for offset,power,duration in [(0,1,.017),(.043,.68,.013),(.087,.32,.015)]:weight+=max(0,min(t+1/30,at+offset+duration)-max(t,at+offset))*30*power
  if weight<=0:continue
  for mat,energy in [(core,100),(branchmat,34),(corona,9)]:mat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value=energy*weight
  primary=max(0,min(t+1/30,at+.017)-max(t,at))>0
  selected_forks=np.arange(len(forks)) if primary else np.arange(len(forks))[np.arange(len(forks))%3!=1]
  selected_fine=np.arange(len(fine)) if primary else np.arange(len(fine))[np.arange(len(fine))%4==0]
  objects.extend([scene.curve('Return stroke',trunks,rr,core),scene.curve('Participating branch channels',[forks[i] for i in selected_forks],[fr[i] for i in selected_forks],branchmat),scene.curve('Secondary corona channels',[fine[i] for i in selected_fine],[finer[i] for i in selected_fine],corona)])
 finish(s,K,f)
