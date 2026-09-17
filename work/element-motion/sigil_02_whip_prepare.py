"""A volume-aware swept water whip. Guide motion is authored; FLIP transports it."""
from pathlib import Path
import json, shutil
import numpy as np
from scipy.interpolate import CubicSpline
R=Path(__file__).resolve().parent
O=R/'sigil-02-water-whip';O.mkdir(exist_ok=True)
# Coordinates are x, height, depth. The tip first hooks back toward the viewer,
# then throws across the frame; the trailing mass follows a smaller turn.
times=np.array([0,.55,1.25,1.95,2.65,3.4,4.5,6.0])
poses=np.array([
 [[-4.2,.26,.9],[-3.5,.26,1.4],[-2.2,.26,1.35],[-1.3,.26,.65],[-1.2,.26,-.25],[-2,.26,-.8],[-3.1,.26,-.75]],
 [[-4.2,.27,.9],[-3.5,.28,1.4],[-2.2,.32,1.2],[-1.35,.55,.5],[-1.5,.8,-.35],[-2.3,1.15,-.85],[-3.15,1.55,-.65]],
 [[-4.1,.34,.85],[-3.5,.65,1.3],[-2.7,1.5,1.05],[-2.4,2.65,.3],[-3.,3.35,-.45],[-4.,3.05,-.95],[-4.2,2.2,-1.05]],
 [[-4.,.6,.9],[-3.2,1.1,1.15],[-2.65,2.35,.8],[-1.6,3.35,.1],[-.3,3.45,-.65],[.9,2.9,-1.15],[1.2,2.05,-1.35]],
 [[-3.95,1.2,.75],[-3.2,1.85,.65],[-2.65,2.7,.4],[-1.4,3.,.2],[.2,2.6,-.55],[2.5,1.8,-.85],[4.15,2.4,-.15]],
 [[-4.05,1.8,.2],[-3.4,2.5,.4],[-2.,2.9,.1],[-.5,2.2,-.4],[1.1,1.65,-.5],[2.8,2.,.2],[4.15,2.8,.6]],
 [[-4.05,1.9,.1],[-3.4,2.45,.2],[-2.,2.55,.1],[-.5,2.15,-.2],[1.1,1.95,-.25],[2.8,2.2,.1],[4.15,2.6,.25]],
 [[-4.05,1.9,.1],[-3.4,2.45,.2],[-2.,2.55,.1],[-.5,2.15,-.2],[1.1,1.95,-.25],[2.8,2.2,.1],[4.15,2.6,.25]]
])
motion=CubicSpline(times,poses,axis=0,bc_type='clamped')
grid=np.linspace(0,1,1201);mass=np.linspace(0,1,257)
smooth=lambda x:np.clip(x,0,1)**2*(3-2*np.clip(x,0,1))
def frame(t,volume):
 cp=motion(t);chord=np.r_[0,np.cumsum(np.linalg.norm(np.diff(cp,axis=0),axis=1))];chord/=chord[-1]
 curve=CubicSpline(chord,cp,axis=0,bc_type='natural')(grid)
 arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(curve,axis=0),axis=1))];length=arc[-1];arc/=length
 # Rounded ends and an equal-volume longitudinal map prevent tube end caps,
 # particle pile-up and a uniformly thick garden-hose silhouette.
 width=np.maximum(0,np.sin(np.pi*grid))**.55
 cdf=np.r_[0,np.cumsum((width[1:]**2+width[:-1]**2)*.5*np.diff(grid))];integral=cdf[-1];cdf/=integral
 longitudinal=np.interp(mass,cdf,grid)
 center=np.stack([np.interp(longitudinal,arc,curve[:,a]) for a in range(3)],axis=1)
 radius=np.interp(longitudinal,grid,width)*np.sqrt(volume/(np.pi*length*integral))
 tangent=np.gradient(center,axis=0);tangent/=np.linalg.norm(tangent,axis=1)[:,None]
 normal=np.empty_like(tangent);normal[0]=[0,1,0];normal[0]-=tangent[0]*np.dot(normal[0],tangent[0]);normal[0]/=np.linalg.norm(normal[0])
 for i in range(1,len(tangent)):
  v=np.cross(tangent[i-1],tangent[i]);c=np.dot(tangent[i-1],tangent[i]);n=normal[i-1]
  normal[i]=n+np.cross(v,n)+np.cross(v,np.cross(v,n))/max(1e-6,1+c)
  normal[i]-=tangent[i]*np.dot(normal[i],tangent[i]);normal[i]/=np.linalg.norm(normal[i])
 binormal=np.cross(tangent,normal)
 flatten=.52+.48*smooth((t-.3)/1.2)
 bank=.45*smooth((t-.5)/.8)*(1-smooth((t-3.1)/1.5))*(mass-.25)
 n=normal*np.cos(bank[:,None])+binormal*np.sin(bank[:,None]);b=binormal*np.cos(bank[:,None])-normal*np.sin(bank[:,None])
 return np.concatenate([center,n*radius[:,None]*flatten,b*radius[:,None]/flatten],axis=1)
for mode in ['cpu','full']:
 base=R/'sigil-02-bending-ground'/mode;out=O/mode;out.mkdir(exist_ok=True)
 cfg=json.loads((base/'config.json').read_text());cfg['frames']=180 if mode=='cpu' else 390
 cfg['guideDt']=.025;cfg['guideSamples']=257;cfg['guideTimes']=241;cfg['forceRoot']=str(base.resolve())
 (out/'config.json').write_text(json.dumps(cfg,indent=2))
 source=np.fromfile(base/'parcels.f32',dtype='<f4').reshape(-1,9).copy()
 volume=len(source)*(cfg['h']*.5/cfg['spaceScale'])**3
 table=np.stack([frame(t,volume) for t in np.arange(241)*.025]).astype('<f4');table.tofile(out/'whip.f32')
 u=source[:,6]*256;lo=np.minimum(u.astype(int),255);a=(u-lo)[:,None]
 basis=table[0,lo]*(1-a)+table[0,lo+1]*a
 initial=basis[:,:3]+basis[:,3:6]*source[:,7:8]+basis[:,6:9]*source[:,8:9]
 rng=np.random.default_rng(7123);initial+=rng.uniform(-cfg['h']*.06,cfg['h']*.06,initial.shape)/.35
 source[:,:3]=initial*.35+cfg['origin'];source.tofile(out/'parcels.f32')
 shutil.copy2(base/'guides.npz',out/'guides.npz')
 assert initial[:,1].min()>0 and np.isfinite(table).all()
 (out/'source-report.json').write_text(json.dumps(dict(particles=len(source),worldVolume=volume,initialMinimumHeight=float(initial[:,1].min()),source='Rounded ground crescent; banked hooked lift; accelerating cast; trailing unfurl',limits='Authored external guide accelerations; native closed-mass FLIP, pressure, surface and floor response.'),indent=2))
print('Prepared CPU and full-resolution whip guides. No simulation/render started.')
