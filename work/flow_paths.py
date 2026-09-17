"""Authored gas trajectories; these curves never become a fuel mask or mesh."""
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.spatial import cKDTree

def spline(points):
    p=np.array(points,float)
    t=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    return CubicSpline(t,p,axis=0,bc_type='natural')(np.linspace(0,t[-1],500))

def paths():
    theta=np.linspace(.24*np.pi,1.76*np.pi,400)
    c=np.c_[.39+.37*np.cos(theta),.47+.45*np.sin(theta)]
    glyphs=[
      [c],
      [spline([[.03,.94],[.19,.60],[.49,.24]]),spline([[.76,.94],[.62,.54],[.41,.05],[.28,-.34],[.03,-.45]])],
      [spline([[.04,1.42],[.04,.74],[.04,.02]]),np.c_[.40+.36*np.cos(np.linspace(1.5*np.pi,3.5*np.pi,500)),.46+.44*np.sin(np.linspace(1.5*np.pi,3.5*np.pi,500))]],
      [spline([[.05,.01],[.05,.43],[.08,.80],[.36,.90],[.71,.78]])],
      [spline([[.75,1.42],[.75,.73],[.75,.02]]),np.c_[.39+.36*np.cos(np.linspace(1.5*np.pi,-.5*np.pi,500)),.46+.44*np.sin(np.linspace(1.5*np.pi,-.5*np.pi,500))]],
      [spline([[.03,.46],[.36,.46],[.75,.46],[.65,.81],[.33,.93],[.03,.67],[.02,.28],[.34,.02],[.72,.15]])],
      [spline([[.15,1.42],[.15,.80],[.15,.15],[.27,.02],[.55,.04]])],
      [spline([[.28,.93],[.28,.50],[.28,.02]]),np.c_[.28+.055*np.cos(np.linspace(0,2*np.pi,120)),1.25+.055*np.sin(np.linspace(0,2*np.pi,120))]],
      [c]
    ]
    out=[]
    offsets=np.array([0,1,2.05,3.12,4.16,5.23,6.28,7.1,7.78])
    for letter,curves in enumerate(glyphs):
        for curve in curves:
            p=curve.copy();p[:,0]+=offsets[letter]-4.32;p[:,1]+=1.42
            dist=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
            tangent=np.gradient(p,axis=0);tangent/=np.maximum(1e-8,np.linalg.norm(tangent,axis=1))[:,None]
            out.append(dict(letter=letter,points=p,tangent=tangent,length=dist[-1],speed=max(.7,dist[-1]/1.12),start=.38+letter*.055))
    return out

def fields(x,z):
    curves=paths();p=np.concatenate([v['points'] for v in curves]);tangent=np.concatenate([v['tangent']*v['speed'] for v in curves])
    ids=np.concatenate([np.full(len(v['points']),i) for i,v in enumerate(curves)])
    grid=np.stack(np.meshgrid(x,z,indexing='xy'),axis=-1)
    distance,idx=cKDTree(p).query(grid)
    return curves,grid,p[idx],tangent[idx],distance,ids[idx]
