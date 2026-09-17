"""Deterministic CPU single scattering over the simulated condensate grid.

Uses Beer-Lambert extinction, HG phase and volume light attenuation. Surface
occlusion comes from Mitsuba depth. Area lights and hot patches use point
quadrature; multiple scattering and volume-to-surface feedback are omitted.
"""
import numpy as np
from scipy.ndimage import map_coordinates
from lava_radiation import radiance

def integrate(surface,depth,cache,eye,target,fov,light_gain=.14,steps=72):
    a=np.load(cache);density=a['density']*.20;origin=a['origin'];extent=a['extent'];shape=np.array(density.shape)
    grid=np.moveaxis(np.indices(density.shape),0,-1);p=origin+(grid+.5)/shape*extent
    eye=np.array(eye);forward=np.array(target)-eye;forward/=np.linalg.norm(forward)
    right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward)
    height,width=surface.shape[:2];yy,xx=np.indices((height,width))
    sx=(2*(xx+.5)/width-1)*np.tan(np.deg2rad(fov/2));sy=(1-2*(yy+.5)/height)*np.tan(np.deg2rad(fov/2))*height/width
    rays=forward+sx[:,:,None]*right+sy[:,:,None]*up;rays/=np.linalg.norm(rays,axis=-1)[:,:,None]
    def sample(field,points):
        coord=np.moveaxis((points-origin)/extent*shape-.5,-1,0)
        return map_coordinates(field,coord,order=1,mode='constant',cval=0)
    to_eye=eye-p;to_eye/=np.linalg.norm(to_eye,axis=-1)[...,None]
    lighting=np.zeros(p.shape);lights=[]
    for offset,size,color in [([-1.1,.75,-.6],[1.,.3],[60.,62.,65.]),([1.,.4,-.4],[.18,.85],[12.,11.,10.])]:
        loc=eye-right*offset[0]+up*offset[1]+forward*offset[2]
        lights.append((loc,np.array(color)*light_gain*(4*size[0]*size[1])))
    for loc in [[-.62,-.07,.27],[-.20,-.09,.23],[.21,-.05,.18],[.48,.06,.15]]:
        lights.append((np.array(loc),np.asarray(radiance(1390))*.04))
    for loc,power in lights:
        delta=loc-p;dist=np.linalg.norm(delta,axis=-1);direction=delta/np.maximum(dist[...,None],.05)
        optical=np.zeros(density.shape)
        for t in (np.arange(20)+.5)/20:optical+=sample(density,p+delta*t)*dist/20
        cosine=-np.sum(direction*to_eye,axis=-1);g=.35;phase=(1-g*g)/(4*np.pi*(1+g*g-2*g*cosine)**1.5)
        lighting+=np.exp(-optical)[...,None]*power/np.maximum(dist[...,None]**2,.025)*phase[...,None]
    lighting*=.94
    inv=np.divide(1.,rays,out=np.full_like(rays,1e10),where=np.abs(rays)>1e-9)
    ends=np.stack([(origin-eye)*inv,(origin+extent-eye)*inv]);near=np.maximum(np.min(ends,axis=0).max(-1),0);far=np.max(ends,axis=0).min(-1)
    valid=far>near;surface_distance=np.where(depth>0,depth,np.inf);far=np.minimum(far,surface_distance)
    ds=np.maximum(far-near,0)/steps;trans=np.ones((height,width));scatter=np.zeros_like(surface,dtype='f8');optical=np.zeros_like(trans)
    for step in range(steps):
        pos=eye+rays*(near+(step+.5)*ds)[:,:,None];sigma=sample(density,pos);tau=sigma*ds;atten=np.exp(-tau)
        emission=np.stack([sample(lighting[:,:,:,c],pos) for c in range(3)],axis=-1)
        scatter+=trans[:,:,None]*(1-atten)[:,:,None]*emission
        trans*=atten;optical+=tau
    result=surface*trans[:,:,None]+scatter
    return result,{'model':'Deterministic CPU single scattering, Beer-Lambert extinction, HG phase, volume self-shadowing and Mitsuba surface depth','densityScale':.20,'steps':steps,'maxOpticalDepth':float(optical.max()),'nonzeroVolumePixels':int((optical>0).sum()),'limits':'Area lights and hot patches approximated by point quadrature; no multiple scattering or volume-to-surface feedback'}
