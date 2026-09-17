"""Bounded water-only hold study. Preserve delivered media; change physics and representation."""
from pathlib import Path
import json,numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent;OLD=R/'sigil-02-repair';O=R/'sigil-02-water-hold';O.mkdir(exist_ok=True)
contract=dict(scope='Water02 only',defects=['Form disperses immediately after writing','Manufactured fragment cloud reads as particles'],goal='Moving coherent water around02 through5.8s, then physical release; no point-cloud spray',iterations=2,pilotFrames=[45,75,120,165],capture='Native FLIP states and CPU Cycles images, then short motion preview',gates=['Finite converged pressure solves','Source/outflow accounting','Coherent form at5.5s','Surface movement during hold','No visible point/sprite cloud','Black background and exit'],forceDisclosure='Authored smooth bending force around variable-width3D guide tubes; no per-particle position targets or render masks',representation='Resolved reconstructed fluid surface; isolated under-resolved markers are not rendered as spheres or multiplied into fragments')
(O/'contract.json').write_text(json.dumps(contract,indent=2))
# Retain every video and source. Reclaim only a regenerable raw cache from the
# water revision that the user has rejected. Never recurse or traverse outside it.
folder=(OLD/'water-release-particles').resolve();assert folder.parent==OLD.resolve()
assert (OLD/'water-candidate.mp4').exists() and (R/'sigil_02_water_release.mjs').exists()
files=list(folder.glob('*.gz'));size=sum(p.stat().st_size for p in files)
for p in files:
 assert p.resolve().parent==folder;p.unlink()
(OLD/'raw-cache-retired.json').write_text(json.dumps({'files':len(files),'bytes':size,'reason':'User rejected water-r2; regenerated raw primary states reclaimed for the revised hold study. Manifest, code, images and all videos retained.'},indent=2))
# Same tapered source geometry; lower energy, with depth centered in a narrower
# domain. This reduces wasted empty-grid work without changing spatial resolution.
a=np.fromfile(OLD/'water-source.f32','<f4').reshape(-1,7).copy();a[:,3]+=.432-.756;a[:,4:]*=.28;a.tofile(O/'source.f32')
cfg=dict(h=.018,nx=234,ny=160,nz=48,extent=[4.212,2.88,.864],origin=[2.1,.98,.432],spaceScale=.35,timeScale=.4)
(O/'config.json').write_text(json.dumps(cfg,indent=2))
guides=json.loads((OLD/'lightning-guides.json').read_text());points=[];widths=[]
for g in guides:
 p=np.array(g['points']);p[:,1]=.38*np.sin(p[:,0]*1.10)+.09*np.sin(p[:,2]*3+p[:,0]*2)
 d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];q=np.arange(0,d[-1]+.001,.015)
 v=np.column_stack([np.interp(q,d,p[:,j]) for j in range(3)]);v=gaussian_filter1d(v,.75,axis=0,mode='nearest')
 points.append(v[:,[0,2,1]]*.35+cfg['origin']);widths.append(np.clip(np.interp(q,d,g['widths'])*.92,.035,.26)*.35)
p=np.concatenate(points);rad=np.concatenate(widths);tree=cKDTree(p);np.savez_compressed(O/'guides.npz',points=p,radii=rad)
shape=(cfg['nx']+1,cfg['ny']+1,cfg['nz']+1);grid=np.indices(shape,dtype=np.float32).reshape(3,-1).T
for c in range(3):
 offset=np.full(3,.5);offset[c]=0;xyz=(grid+offset)*cfg['h'];distance,ids=tree.query(xyz,workers=2);delta=xyz-p[ids];unit=delta/np.maximum(distance[:,None],1e-8);radius=rad[ids]
 # Broad smooth potential around the stream, with a soft free interior. Fluid
 # circulates tangentially; radial energy is gently damped during the hold.
 band=np.exp(-np.maximum(0,distance/radius-2.2)**2)
 force=-110*np.maximum(0,distance-radius*.65)*unit[:,c]*band
 damping=1.3*unit[:,c]**2*band
 np.column_stack((force,damping)).astype('<f4').tofile(O/f'guide-{c}.f32')
(O/'source-report.json').write_text(json.dumps(dict(particles=len(a),medianSpeed=float(np.median(np.linalg.norm(a[:,4:],axis=1))),writeEnds=float(a[:,0].max()),holdUntil=5.8,releaseEnds=6.65,field='Smooth radial potential on MAC faces, applied before pressure projection; no frozen vertices or image silhouette clipping'),indent=2))
audit=OLD/'water-audit.json';j=json.loads(audit.read_text());j['visualStatus']='user-rejected';j['userFeedback']='Water is really bad, does not hold its form long enough, drops look like particles.';audit.write_text(json.dumps(j,indent=2))
print(json.dumps({'sourceParticles':len(a),'grid':shape,'cacheBytesReclaimed':size,'pilotFrames':contract['pilotFrames']}))
