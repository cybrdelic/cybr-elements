"""Guided 3D Laplacian growth and exposed discharge events.

Point-charge growth follows Kim et al. CG&A 2007 equations 10--13.
The moving attraction field and corridor are authored bending controls.
This is a graphics approximation, not a calibrated plasma solver.
"""
import os
os.environ.setdefault('NUMBA_NUM_THREADS','2')
os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
from pathlib import Path
import numpy as np, cv2, json, sys, time, subprocess, importlib.util
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter, map_coordinates, distance_transform_edt
from scipy.fft import rfftn,irfftn
from PIL import Image
from shared_motion import pose
R=Path(__file__).resolve().parent;B=R/'sigil-02-repair';OUT=B/'lightning-frames';OUT.mkdir(exist_ok=True)
W,H,FPS=1920,1080,30;cv2.setNumThreads(2)
GUIDES=json.loads((B/'lightning-guides.json').read_text());EVENTS=np.array([g['birth'] for g in GUIDES])
CAM=np.array([.65,-13.,3.05]);TARGET=np.array([0.,0.,1.8]);FORWARD=TARGET-CAM;FORWARD/=np.linalg.norm(FORWARD)
RIGHT=np.cross(FORWARD,[0,0,1]);RIGHT/=np.linalg.norm(RIGHT);UP=np.cross(RIGHT,FORWARD)

def curve(t):
    p=pose(t)[0];return np.array([p[0],.78*np.sin((t-.08)*2*np.pi/1.6+.35),p[1]])

def project(p,w=W,h=H):
    v=p-CAM;z=v@FORWARD
    return np.column_stack((w/2+(v@RIGHT)/z*w*1.25,h/2-(v@UP)/z*w*1.25))

def grow(event):
    dest=B/f'discharge-train-{VARIANT}-{event:02}.npz'
    if dest.exists():
        with np.load(dest) as z:return {k:z[k] for k in z.files}
    rng=np.random.default_rng(18301+event*379+VARIANT*13007)
    guide=np.asarray(GUIDES[event]['points']);widths=np.asarray(GUIDES[event]['widths']);gtree=cKDTree(guide)
    lengths=np.r_[0,np.cumsum(np.linalg.norm(np.diff(guide,axis=0),axis=1))]
    stopd=np.linspace(0,lengths[-1],max(2,int(np.ceil(lengths[-1]/.85))+1))
    stops=np.column_stack([np.interp(stopd,lengths,guide[:,k]) for k in range(3)])
    h=.038;radius=h*.5;cap=110000
    candidates=np.zeros((cap,3));potential=np.zeros(cap);owners=np.zeros(cap,int);live=np.zeros(cap,bool);corridor=np.zeros(cap)
    nodes=[np.round(guide[0]/h)*h];parent=[-1];occupied={tuple(np.round(nodes[0]/h).astype(int))};known={};nc=0
    directions=np.array([(x,y,z) for x in [-1,0,1] for y in [-1,0,1] for z in [-1,0,1] if x or y or z],int)
    def add_candidates(index):
        nonlocal nc
        cell=np.round(nodes[index]/h).astype(int);new=[]
        for direction in directions:
            key=tuple(cell+direction)
            if key in occupied:continue
            if key in known:
                c=known[key]
                if not live[c]:live[c]=True;owners[c]=index;new.append(c)
                continue
            point=np.array(key)*h
            if abs(point[0])>4.9 or point[2]<-.45 or point[2]>4.8 or abs(point[1])>2.1:continue
            known[key]=nc;candidates[nc]=point;owners[nc]=index;live[nc]=True;new.append(nc);nc+=1
        if new:
            positions=candidates[new];charges=np.array(nodes)
            potential[new]=-(radius/np.maximum(np.linalg.norm(positions[:,None]-charges[None],axis=2),radius)).sum(1)
            distance,nearest=gtree.query(positions)
            # A wide control region allows meaningful diverging forks.
            corridor[new]=.008+.992*np.exp(-(distance/(.25+widths[nearest]*.75))**2)
        if nc>=cap-30:raise RuntimeError('Candidate capacity')
    add_candidates(0);stage=1;tip=0;stage_start=0;begun=time.time()
    for step in range(6500):
        ids=np.flatnonzero(live[:nc]);pos=candidates[ids];d=np.linalg.norm(pos-stops[stage],axis=1)
        # Superposed point-charge potential plus moving positive electrode.
        tangent=stops[stage]-stops[stage-1];normal=np.cross(tangent,[0,1,0]);normal/=max(1e-6,np.linalg.norm(normal))
        side=(stops[stage]+stops[stage-1])*.5+normal*(.80 if (stage+event+VARIANT)%2 else -1.0)+np.array([0,.32,0])
        ds=np.linalg.norm(pos-side,axis=1)
        phi=potential[ids]+(.75*(1+(step-stage_start)/400)**2)/np.maximum(d,.08)+.70/np.maximum(ds,.10)
        field=np.maximum(0,(phi-phi.min())/max(1e-10,phi.max()-phi.min()))
        weights=field**2.25*corridor[ids]**.65*np.exp(-np.minimum(d,ds)/1.20)
        c=ids[rng.choice(len(ids),p=weights/weights.sum())];point=candidates[c].copy()
        nodes.append(point);parent.append(int(owners[c]));tip=len(nodes)-1;live[c]=False;occupied.add(tuple(np.round(point/h).astype(int)))
        active=np.flatnonzero(live[:nc]);potential[active]-=radius/np.maximum(np.linalg.norm(candidates[active]-point,axis=1),radius)
        add_candidates(tip)
        if np.linalg.norm(point-stops[stage])<h*2.4:
            stage+=1;stage_start=step
            if stage==len(stops):break
            # Advance the controlled bending tip. Finished side leaders remain
            # in the tree but do not jump ahead and short-circuit a later bend.
            live[:nc]&=owners[:nc]==tip
    if stage!=len(stops):raise RuntimeError(f'Unconnected event {event}, reached {stage}/{len(stops)}')
    p=np.array(nodes);parent=np.array(parent);trunk=np.zeros(len(p),bool);j=tip
    while j>=0:trunk[j]=True;j=parent[j]
    children=[[] for _ in p]
    for j in range(1,len(p)):children[parent[j]].append(j)
    length=np.zeros(len(p));distance=np.zeros(len(p))
    for j in range(1,len(p)):distance[j]=distance[parent[j]]+np.linalg.norm(p[j]-p[parent[j]])
    for j in range(len(p)-1,0,-1):length[parent[j]]=max(length[parent[j]],length[j]+np.linalg.norm(p[j]-p[parent[j]]))
    strength=np.zeros(len(p));strength[trunk]=1.;order=np.full(len(p),3,int);order[trunk]=0
    # Display the competing long leaders, not every microscopic occupied cell.
    roots=[j for j in range(1,len(p)) if not trunk[j] and trunk[parent[j]] and length[j]>.14]
    roots=sorted(roots,key=lambda j:length[j],reverse=True)[:12]
    def light(root,amp,level):
        j=root;total=max(.001,length[root]);selected=[]
        while True:
            strength[j]=max(strength[j],amp*(.12+.88*(length[j]/total)**.6));order[j]=level;selected.append(j)
            if not children[j]:break
            j=max(children[j],key=lambda k:length[k])
        if level==1:
            for k in selected:
                for child in children[k]:
                    if child not in selected and length[child]>.13:light(child,amp*.22,2)
    for root in roots:light(root,min(.38,.11+length[root]*.17),1)
    # Sub-cell irregularity removes grid-aligned silhouettes; connectivity is unchanged.
    p+=rng.uniform(-.30,.30,p.shape)*h
    result=dict(points=p,parent=parent,trunk=trunk,strength=strength,order=order,distance=distance)
    np.savez_compressed(dest,**result)
    print('GROW',event,'nodes',len(p),'trunk',int(trunk.sum()),'forks',len(roots),'depth',round(float(np.ptp(p[:,1])),3),'seconds',round(time.time()-begun,1),flush=True)
    return result

def exposure(f,event):
    # Short leader/return-stroke trains. No standing current between events.
    t=f/FPS;end=t+1/FPS;main=fork=0.
    birth=EVENTS[event]
    trains=[(birth,1.)]+[(at+.008*(event%5),power) for at,power in [(2.03,1.5),(2.77,.70),(3.36,1.2),(4.12,1.0)] if at>birth+.15]
    for at,gain in trains:
        for offset,power,duration in [(0,1.,.006),(.047+(event%3)*.007,.56,.0038),(.14+(event%2)*.02,.20,.0028)]:
            e=max(0,min(end,at+offset+duration)-max(t,at+offset))*FPS
            main+=e*power*gain;fork+=e*power*gain*(1 if offset==0 else .035)
        leader=max(0,min(end,at)-max(t,at-.038))*FPS*.008
        main+=leader;fork+=leader
    return main,fork


def select_net(f,net):
    # A return stroke reuses its channel for milliseconds; a later discharge
    # grows a fresh tree. This avoids repeatedly blinking one fixed wire logo.
    train=int(np.searchsorted([1.99,2.73,3.32,4.08],f/FPS,side='right'))
    return net['versions'][train] if 'versions' in net else net

def channel(f,nets,w=W,h=H):
    field=np.zeros((h,w),np.float32);peak=0.
    for event,net in enumerate(nets):
        net=select_net(f,net)
        energy,branch=exposure(f,event)
        if not energy:continue
        at=EVENTS[event];t=f/FPS;t1=(f+1)/FPS
        leader=max(0,min(t1,at)-max(t,at-.055))*FPS*.012
        stroke=max(0,energy-leader);branchStroke=max(0,branch-leader)
        trunkLength=max(net['distance'][net['trunk']].max(),.001)
        peak=max(peak,energy)
        points=net['points'].copy();children=[[] for _ in points]
        for j in range(1,len(points)):children[net['parent'][j]].append(j)
        # Remove the unresolved lattice scale while retaining all fork junctions.
        for _ in range(2):
            q=points.copy()
            for j in range(1,len(points)):
                lit=[c for c in children[j] if net['strength'][c]>0]
                if len(lit)==1 and net['strength'][j]>0:q[j]=points[j]*.60+.20*(points[net['parent'][j]]+points[lit[0]])
            points=q
        p=project(points,w,h)
        for j in np.flatnonzero(net['strength']):
            if j==0:continue
            arrival=at-.055+.055*min(1.2,net['distance'][j]/trunkLength)
            advancing=max(0,min(t1,at)-max(t,arrival))*FPS*.012
            power=((stroke if net['trunk'][j] else branchStroke)+advancing)*net['strength'][j]
            if power<=0:continue
            radius=(.42 if net['trunk'][j] else .12)*w/W
            a=p[net['parent'][j]];b=p[j];lo=np.maximum(0,np.floor(np.minimum(a,b)-3*radius-1)).astype(int);hi=np.minimum([w,h],np.ceil(np.maximum(a,b)+3*radius+1)).astype(int)
            if np.any(hi<=lo):continue
            yy,xx=np.mgrid[lo[1]:hi[1],lo[0]:hi[0]];segment=b-a;u=np.clip(((xx-a[0])*segment[0]+(yy-a[1])*segment[1])/max(1e-8,np.sum(segment*segment)),0,1)
            ds=(xx-a[0]-u*segment[0])**2+(yy-a[1]-u*segment[1])**2
            profile=power*np.exp(-ds/(2*radius*radius))
            patch=field[lo[1]:hi[1],lo[0]:hi[0]];np.maximum(patch,profile,out=patch)
    return field,peak

class Aerosol:
    def __init__(self):
        self.shape=(48,112,200);self.spacing=np.array([4.4/47,5.90625/111,10.5/199]);self.grid=np.indices(self.shape,dtype=np.float32)
        self.world=np.array([(self.grid[2]/199-.5)*10.5,(self.grid[0]/47-.5)*4.4,1.903125+(.5-self.grid[1]/111)*5.90625])
        self.rho=np.zeros(self.shape,np.float32);self.heat=self.rho.copy();self.v=np.zeros((3,*self.shape),np.float32)
        rng=np.random.default_rng(8719);a=np.stack([gaussian_filter(rng.normal(size=self.shape),3) for _ in range(3)]).astype(np.float32)
        self.v[0]=(np.gradient(a[2],self.spacing[1],axis=1)-np.gradient(a[1],self.spacing[2],axis=2))*1.8
        self.v[1]=(np.gradient(a[0],self.spacing[2],axis=2)-np.gradient(a[2],self.spacing[0],axis=0))*1.8
        self.v[2]=(np.gradient(a[1],self.spacing[0],axis=0)-np.gradient(a[0],self.spacing[1],axis=1))*1.8
        noise=gaussian_filter(rng.normal(size=self.shape),1.3);self.noise=np.exp(noise/noise.std()*.65)
        self.k=np.array(np.meshgrid(*[np.sin(2*np.pi*(np.fft.rfftfreq(n) if i==2 else np.fft.fftfreq(n)))/self.spacing[i] for i,n in enumerate(self.shape)],indexing='ij'));self.k2=np.sum(self.k*self.k,axis=0);self.k2[0,0,0]=1;self.rows=[]
        yy,xx=np.indices((112,200));ray=FORWARD[:,None,None]+RIGHT[:,None,None]*((xx/200-.5)/1.25)+UP[:,None,None]*((.5-yy/112)*112/200/1.25)
        self.rays=[]
        for depth in np.linspace(-2.15,2.15,48):
            pos=CAM[:,None,None]+ray*((depth-CAM[1])/ray[1])
            self.rays.append(np.array([(pos[1]/4.4+.5)*47,(.5-(pos[2]-1.903125)/5.90625)*111,(pos[0]/10.5+.5)*199]))
    def step(self,f,nets):
        on=1.;nozzle=np.zeros(self.shape,np.float32)
        light=np.zeros(self.shape,np.float32)
        for e,net in enumerate(nets):
            net=select_net(f,net)
            energy,branch=exposure(f,e)
            if energy<=0:continue
            p=net['points'][net['trunk']];coords=np.column_stack(((p[:,1]/4.4+.5)*47,(.5-(p[:,2]-1.903125)/5.90625)*111,(p[:,0]/10.5+.5)*199)).round().astype(int)
            coords=np.clip(coords,0,np.array(self.shape)-1);mask=np.ones(self.shape,bool);mask[tuple(coords.T)]=False
            d=distance_transform_edt(mask,sampling=self.spacing);light+=energy*np.exp(-d/.28)/(.012+d*d);nozzle+=energy*np.exp(-(d/.09)**2)*self.noise*.22
        for _ in range(2):
            dt=1/60;lookup=self.grid-self.v*dt/self.spacing[:,None,None,None]
            self.rho=map_coordinates(self.rho,lookup,order=1,mode='constant');self.heat=map_coordinates(self.heat,lookup,order=1,mode='constant');self.v=np.stack([map_coordinates(v,lookup,order=1,mode='constant') for v in self.v])
            self.rho+=nozzle*.9*dt*on;self.rho*=np.exp(-1.1*dt);self.heat+=light*.3*dt;self.heat*=np.exp(-4*dt)
            self.v[1]-=(self.heat*2+self.rho*.6)*dt
            spectra=np.stack([rfftn(v,workers=2) for v in self.v]);dot=np.sum(spectra*self.k,axis=0)/np.maximum(self.k2,1e-12);spectra-=self.k*dot;self.v=np.stack([irfftn(v,s=self.shape,workers=2) for v in spectra]).astype(np.float32)
        densitylight=self.rho*(light+.005);scatter=sum(map_coordinates(densitylight,c,order=1,mode='constant') for c in self.rays)*self.spacing[0]
        if f%20==0:self.rows.append(dict(frame=f,finite=bool(np.isfinite(self.v).all()),aerosolMass=float(self.rho.sum()*np.prod(self.spacing)),maxSpeed=float(np.linalg.norm(self.v,axis=0).max())))
        return cv2.resize(scatter,(W,H),interpolation=cv2.INTER_CUBIC)

def render(f,nets,aerosol=None):
    field,peak=channel(f,nets,W*2,H*2);core=cv2.resize(field,(W,H),interpolation=cv2.INTER_AREA)*230
    near=cv2.GaussianBlur(core,(0,0),.65);halo=cv2.GaussianBlur(core,(0,0),3.8);bloom=cv2.GaussianBlur(core,(0,0),14)
    scatter=aerosol.step(f,nets) if aerosol else 0.
    linear=core[:,:,None]*np.array([1,.98,1],np.float32)+near[:,:,None]*np.array([.19,.19,.23],np.float32)+halo[:,:,None]*np.array([.014,.018,.042],np.float32)+bloom[:,:,None]*np.array([.003,.004,.012],np.float32)
    if aerosol:linear+=scatter[:,:,None]*np.array([.075,.085,.13],np.float32)
    rgb=1-np.exp(-np.maximum(linear,0));rgb=np.where(rgb<=.0031308,12.92*rgb,1.055*rgb**(1/2.4)-.055)
    return np.rint(np.clip(rgb,0,1)*255).astype(np.uint8)

if __name__=='__main__':
    started=time.time();families=[]
    for VARIANT in range(5):families.append([grow(i) for i in range(len(EVENTS))])
    nets=[dict(families[0][i],versions=[family[i] for family in families]) for i in range(len(EVENTS))]
    if '--full' not in sys.argv:
        frames=[12,30,49,61,83,102];sheet=Image.new('RGB',(1440,810))
        for i,f in enumerate(frames):
            im=Image.fromarray(render(f,nets));im.resize((720,405)).save(OUT/f'pilot-{f:04}.jpg');sheet.paste(im.resize((480,270)),((i%3)*480,(i//3)*270))
        sheet=sheet.crop((0,0,1440,540));sheet.save(B/'lightning-pilot-fresh-channels.jpg',quality=94);print('Pilot ready',flush=True);sys.exit(0)
    aerosol=Aerosol();enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r','30','-i','-','-vf','scale=in_range=full:out_range=tv:out_color_matrix=bt709','-c:v','libx264','-threads','2','-preset','slow','-crf','15','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart',str(B/'lightning-candidate.mp4')],stdin=subprocess.PIPE)
    for f in range(168):
        pixels=render(f,nets,aerosol);enc.stdin.write(pixels.tobytes())
        if f in [12,30,49,61,62,83,84,101,102,124,125,145,167]:Image.fromarray(pixels).resize((1280,720)).save(OUT/f'{f:04}.jpg',quality=95)
        if f%20==0:print('FRAME',f,'seconds',round(time.time()-started,1),flush=True)
    enc.stdin.close();assert enc.wait()==0
    report=dict(model='Local moving 3D point-charge discharges, advancing leaders, stable return-stroke channels; authored guidance and approximate aerosol scattering',events=EVENTS.tolist(),frames=168,seconds=time.time()-started,aerosol=aerosol.rows,networks=[dict(nodes=len(n['points']),depthRange=float(np.ptp(n['points'][:,1])),finite=bool(np.isfinite(n['points']).all()),connected=bool(np.all(n['parent'][1:]<np.arange(1,len(n['parent']))))) for n in nets])
    (B/'lightning-report.json').write_text(json.dumps(report,indent=2));print('COMPLETE',flush=True)
