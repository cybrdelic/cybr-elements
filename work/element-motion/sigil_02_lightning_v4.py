"""Branched electrode networks with load-dependent current and native optics.

An art-directed discharge graph, not a calibrated plasma simulation. The full
02 material volume seeds the conductors; forks leave it without clipping.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='2';os.environ['OMP_NUM_THREADS']='2'
from pathlib import Path
import ast,sys,json,time,subprocess
import numpy as np,cv2
from PIL import Image
from scipy.ndimage import map_coordinates,distance_transform_edt
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import minimum_spanning_tree,breadth_first_order
R=Path(__file__).resolve().parent;B=R/'sigil-02-elements/lightning-v4';B.mkdir(exist_ok=True);OUT=B/'frames';OUT.mkdir(exist_ok=True)
native=(R/'bending-lightning-v5.py').read_text();ns={'__file__':str(R/'bending-lightning-v5.py')};exec(native[:native.index('if __name__')],ns)
source=np.load(R/'sigil-02-v2/source.npz');fields={k:source[k] for k in source.files};mask=(fields['support']>.5).astype('uint8');Z,X=mask.shape
count,labels,stats,_=cv2.connectedComponentsWithStats(mask);rng=np.random.default_rng(68715);nets=[];events=[]
def sample(field,p):return map_coordinates(fields[field],[(p[:,2]+1.05)/7.875*(Z-1),(p[:,0]+7)/14*(X-1)],order=1,mode='nearest')
for component in range(1,count):
 if stats[component,4]<20:continue
 yy,xx=np.where(labels==component);take=np.arange(0,len(xx),5);rng.shuffle(take);take=take[:1800]
 p=np.column_stack((xx[take]/(X-1)*14-7,rng.normal(0,.085,len(take)),yy[take]/(Z-1)*7.875-1.05))
 # A sparse 3D electrode cloud covers the complete tapered stroke width.
 chosen=[]
 for q in p:
  if not chosen or np.linalg.norm(np.asarray(chosen)-q,axis=1).min()>.065:chosen.append(q)
 p=np.asarray(chosen);tree=cKDTree(p);dist,near=tree.query(p,k=min(10,len(p)));rows=np.repeat(np.arange(len(p)),near.shape[1]-1);cols=near[:,1:].ravel();weights=dist[:,1:].ravel()
 weights*=rng.uniform(.72,1.28,len(weights));graph=coo_matrix((weights,(rows,cols)),shape=(len(p),len(p))).tocsr();graph=graph.maximum(graph.T)
 mst=minimum_spanning_tree(graph);root=int(np.argmin(p[:,0]));order,pred=breadth_first_order(mst+mst.T,root,directed=False,return_predecessors=True)
 if len(order)<len(p):p=p[order];tree=cKDTree(p);dist,near=tree.query(p,k=min(12,len(p)));rr=np.repeat(np.arange(len(p)),near.shape[1]-1);cc=near[:,1:].ravel();g=coo_matrix((dist[:,1:].ravel(),(rr,cc)),shape=(len(p),len(p))).tocsr();mst=minimum_spanning_tree(g.maximum(g.T));order,pred=breadth_first_order(mst+mst.T,0,directed=False,return_predecessors=True)
 inverse=np.empty(len(p),int);inverse[order]=np.arange(len(p));p=p[order];parent=np.r_[-1,inverse[pred[order[1:]]]];children=np.bincount(parent[1:],minlength=len(p));leaves=np.flatnonzero(children==0)
 points=list(p);parents=list(parent);outside=[]
 for leaf in leaves[::max(1,len(leaves)//18)]:
  current=int(leaf);direction=p[leaf]-p[parent[leaf]];direction/=max(1e-9,np.linalg.norm(direction));length=rng.uniform(.25,.72)
  for j in range(max(2,int(length/.055))):
   direction=direction*.8+rng.normal(0,.27,3);direction/=np.linalg.norm(direction);q=points[current]+direction*.055;parents.append(current);points.append(q);current=len(points)-1;outside.append(current)
 p=np.array(points);parent=np.array(parents);load=np.ones(len(p));distance=np.zeros(len(p))
 for j in range(len(p)-1,0,-1):load[parent[j]]+=load[j]
 for j in range(1,len(p)):distance[j]=distance[parent[j]]+np.linalg.norm(p[j]-p[parent[j]])
 trunk=np.zeros(len(p),bool);tip=int(np.argmax(distance));j=tip
 while j>=0:trunk[j]=True;j=parent[j]
 strength=.018+.78*(load/load.max())**.58
 strength[trunk]=np.maximum(strength[trunk],.65)
 strength[np.asarray(outside,dtype=int)]*=.65
 orderlevel=np.where(trunk,0,1);arrival=np.clip(sample('arrival',p),.3,3.9)
 net=dict(points=p,parent=parent,trunk=trunk,strength=strength,order=orderlevel,distance=distance,arrival=arrival)
 nets.append(net);events.append(float(arrival.min())+.08);np.savez_compressed(B/f'network-{component}.npz',**net)
EVENTS=np.asarray(events);ns.update(B=B,OUT=OUT,EVENTS=EVENTS)
def project(p,w=1920,h=1080):return np.column_stack(((p[:,0]/14+.5)*w,(.5-(p[:,2]-2.8875)/7.875)*h))
def exposure(f,event):
 t=f/30;end=t+1/30;main=fork=0.
 schedule=[]
 for at,power in [(.42,.5),(.87,.7),(1.38,.6),(1.88,.8),(2.37,.6),(2.89,.85),(3.42,.65),(3.91,.7),(4.20,.85),(4.73,.55),(5.34,1.),(5.92,.65),(6.48,1.),(6.82,.45)]:schedule.extend([(at+.002*event,power,.014),(at+.060,power*.40,.010),(at+.11,power*.16,.008)])
 for at,power,duration in schedule:
  e=max(0,min(end,at+duration)-max(t,at))*30;main+=e*power;fork+=e*power
 if .3<t<6.85:main+=.005*(.6+.4*np.sin(t*93+event)**2);fork+=.0015
 return main,fork
ns['project']=project;ns['exposure']=exposure
tree=ast.parse(native)
def fn(name):return ast.get_source_segment(native,next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name))
channel=fn('channel');channel=channel.replace('            if power<=0:continue','            power*=float(net[\'arrival\'][j]<=t1)\n            if power<=0:continue')
# Retain native subpixel profiles; avoid the original smoothing that made the
# short contour electrodes read as neon tubing.
channel=channel.replace('for _ in range(2):','for _ in range(0):')
exec(channel,ns)
aero=fn('Aerosol').replace('10.5','14.0').replace('5.90625','7.875').replace('1.903125','2.8875');a=aero.index('        on=pose(f/30)');b=aero.index('        light=',a)
aero=aero[:a]+'''        on=float(.3<f/30<7.0)
        nozzle=np.exp(-self.source_distance/.07)*self.noise
''' + aero[b:]
ns.update(CAM=np.array([0.,-13.,2.8875]),TARGET=np.array([0.,0.,2.8875]),FORWARD=np.array([0.,1.,0.]),RIGHT=np.array([1.,0.,0.]),UP=np.array([0.,0.,1.]))
aero=aero.replace("p=net['points'][net['trunk']];coords=", "p=net['points'][net['trunk'] & (net['arrival'] <= (f+1)/30)]\n            if not len(p):continue\n            coords=")
aero=aero.replace('densitylight=self.rho*(light+.005)','densitylight=self.rho*light')
exec(aero,ns)
render=fn('render').replace('if aerosol:linear+=scatter[:,:,None]*np.array([.26,.31,.43],np.float32)','if aerosol:linear+=scatter[:,:,None]*np.array([.26,.31,.43],np.float32)*.12')
exec(render,ns)
if '--pilot' in sys.argv:
 Image.fromarray(ns['render'](160,nets)).resize((1280,720)).save(B/'pilot.jpg',quality=95);print('Pilot ready',len(nets),sum(len(n['points']) for n in nets));sys.exit(0)
aerosol=ns['Aerosol']();cloud=np.concatenate([n['points'] for n in nets]);co=np.column_stack(((cloud[:,1]/4.4+.5)*47,(.5-(cloud[:,2]-2.8875)/7.875)*111,(cloud[:,0]/14+.5)*199)).round().astype(int);co=np.clip(co,0,np.array(aerosol.shape)-1);support=np.ones(aerosol.shape,bool);support[tuple(co.T)]=False;aerosol.source_distance=distance_transform_edt(support,sampling=aerosol.spacing)
grid=np.indices((112,200));aerosol.rays=[np.array([np.full((112,200),d),grid[0].astype(float),grid[1].astype(float)]) for d in np.linspace(0,47,48)]
started=time.time();video=B.parent/'lightning-02-v4.mp4';enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','-','-c:v','libx264','-threads','2','-preset','fast','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],stdin=subprocess.PIPE)
for f in range(294):
 pixels=ns['render'](f,nets,aerosol);enc.stdin.write(pixels.tobytes())
 if f%5==0 or f in [126,142,160,178,195,205,293]:Image.fromarray(pixels).resize((1280,720)).save(OUT/f'{f:04}.jpg',quality=94)
 if f%30==0:print('FRAME',f,'seconds',round(time.time()-started,1),flush=True)
 if f==75:
  print('LIGHTNING REVIEW GATE',flush=True)
  while not (B.parent/'continue-lightning-v4').exists():time.sleep(.5)
enc.stdin.close();assert enc.wait()==0
(B.parent/'lightning-report-v4.json').write_text(json.dumps({'frames':294,'networks':len(nets),'nodes':sum(len(n['points']) for n in nets),'elapsed':time.time()-started,'aerosol':aerosol.rows,'model':'Art-directed 3D branched conductor graphs, subtree current weighting, geodesic excitation, exposed return strokes and pressure-projected lit aerosol; not calibrated plasma'},indent=2));print('LIGHTNING COMPLETE',flush=True)
