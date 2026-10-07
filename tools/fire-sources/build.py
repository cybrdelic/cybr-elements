"""Bake static solid geometry, never fire frames. X/Z horizontal, Y up, metres.

RGBA16F: signed distance, surface fuel capacity, thermal response, material ID.
The tree proxy comes from the reviewed forest-surface full-mesh export.
"""
from pathlib import Path
import json, hashlib
import numpy as np
from scipy.ndimage import distance_transform_edt

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/objects'
N=64; H=3/N
z,y,x=np.mgrid[:N,:N,:N]; P=(np.stack([x,y,z],-1)+.5)*H-1.5

def box(c,b):
    q=np.abs(P-c)-b
    return np.linalg.norm(np.maximum(q,0),axis=-1)+np.minimum(q.max(-1),0)
def capsule(a,b,r):
    q=P-a; d=np.array(b)-a
    t=np.clip((q*d).sum(-1)/max(float(d@d),1e-9),0,1)
    return np.linalg.norm(q-t[...,None]*d,axis=-1)-r
def sphere(c,r):return np.linalg.norm(P-c,axis=-1)-r

reports=[]
def model(name,make,provenance):
    field=np.zeros((N,N,N,4),np.float32);field[...,0]=10
    def add(d,fuel=1,thermal=1,material=1):
        take=d<field[...,0]
        field[take]=np.stack([d,np.full(d.shape,fuel),np.full(d.shape,thermal),np.full(d.shape,material)],-1)[take]
    make(add)
    assert np.isfinite(field).all() and np.any(field[...,0]<0)
    raw=field.astype('<f2').tobytes();(OUT/(name+'.rgba16.bin')).write_bytes(raw)
    reports.append(dict(id=name,resolution=N,bounds=[-1.5,1.5],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),provenance=provenance))

def house(add):
    # Hollow timber cabin, open door and windows; pitched roof and chimney.
    walls=np.maximum(box([0,-.56,0],[1.12,.66,.8]),-box([0,-.51,0],[.99,.70,.67]))
    walls=np.maximum(walls,-box([-.42,-.78,.8],[.23,.46,.22]))
    for xx in [-.67,.58]:walls=np.maximum(walls,-box([xx,-.37,0],[.23,.24,1]))
    for zz in [-.36,.36]:walls=np.maximum(walls,-box([0,-.36,zz],[1.4,.23,.17]))
    add(walls,1.6,.65,1)
    add(box([0,-1.24,0],[1.18,.08,.88]),1.8,.6,1)
    # Roof is a finite sloped slab rather than a filled triangular prism.
    roof=np.maximum.reduce([np.abs(P[...,1]-(.58-.48*np.abs(P[...,0])))-.065,np.abs(P[...,0])-1.26,np.abs(P[...,2])-.92])
    add(roof,1.3,.8,2)
    chimney=np.maximum(box([.67,.51,-.30],[.15,.48,.17]),-box([.67,.62,-.30],[.08,.5,.10]))
    add(chimney,0,.3,3)
    # Interior wooden furnishing catches heat and supplies fuel through openings.
    add(box([.38,-.98,-.05],[.38,.20,.35]),2,.9,1)
    for xx in [-1.03,1.03]:
        for zz in [-.71,.71]:add(box([xx,-.55,zz],[.055,.70,.055]),1.5,.7,1)

def car(add):
    add(box([0,-.95,0],[1.25,.19,.53])-.045,0,.35,4)
    # Hood and trunk, separate dark cabin, open windows.
    add(box([-.91,-.68,0],[.35,.10,.52])-.025,.45,.7,4)
    add(box([1.01,-.7,0],[.24,.10,.52])-.025,.25,.7,4)
    for zz in [-.51,.51]:add(box([.10,-.65,zz],[.72,.18,.035]),.5,.7,4)
    add(box([.08,-.20,0],[.65,.055,.50])-.025,.25,.6,4)
    for xx in [-.57,.72]:
        for zz in [-.47,.47]:add(capsule([xx,-.64,zz],[xx*.85,-.23,zz],.045),.3,.8,4)
    for xx in [-.8,.82]:
        for zz in [-.57,.57]:
            d=np.maximum(np.linalg.norm(P[...,:2]-[xx,-1.09],axis=-1)-.24,np.abs(P[...,2]-zz)-.12)
            add(d,2,1.1,5)
            add(np.maximum(np.linalg.norm(P[...,:2]-[xx,-1.09],axis=-1)-.12,np.abs(P[...,2]-zz)-.135),0,.4,6)
    for xx in [-.16,.4]:
        for zz in [-.25,.25]:add(box([xx,-.63,zz],[.17,.23,.17]),2,1.15,5)
    add(box([-.83,-.76,0],[.24,.15,.37]),2.2,1.25,5)
    for zz in [-.36,.36]:add(box([-1.29,-.80,zz],[.02,.055,.10]),0,.2,6)

def mannequin(add):
    add(capsule([0,-.4,0],[0,.34,0],.24),1.1,1.0,7)
    add(sphere([0,.81,0],.23),.7,1.1,7)
    add(capsule([0,.32,0],[0,.61,0],.105),.7,1.1,7)
    for side in [-1,1]:
        add(capsule([side*.17,-.44,0],[side*.29,-.86,.05],.115),1.0,1.1,7)
        add(capsule([side*.29,-.86,.05],[side*.32,-1.24,0],.09),.9,1.15,7)
        add(box([side*.32,-1.27,.07],[.11,.065,.18]),.8,1.2,7)
        add(capsule([side*.22,.30,0],[side*.47,-.02,.03],.10),.9,1.15,7)
        add(capsule([side*.47,-.02,.03],[side*.62,-.29,.16],.075),.8,1.2,7)
        add(sphere([side*.64,-.34,.18],.085),.8,1.2,7)

def logs(add):
    for zz in [-.43,0,.43]:add(capsule([-.80,-.47,zz],[.80,-.47,zz],.15),2.3,.8,1)
    for xx in [-.45,.45]:add(capsule([xx,-.19,-.67],[xx,-.19,.67],.14),2,.85,1)
    add(capsule([-.60,.07,-.08],[.65,.07,.16],.13),1.8,.9,1)

OUT.mkdir(parents=True,exist_ok=True)
model('house',house,'Authored hollow timber cabin with open windows, door, pitched roof and inert chimney.')
model('car',car,'Authored test vehicle: inert metal body; combustible seats, tyres and engine contents.')
model('mannequin',mannequin,'Non-anatomical articulated test mannequin with combustible surface coating.')
model('logs',logs,'Cross-stacked solid wood logs; the bonfire and hearth use this geometry as their fuel source.')
# Reuse the reviewed full-mesh export, never the older tree-study proxy.
import runpy
runpy.run_path(str(Path(__file__).with_name('voxelize_forest_tree.py')),run_name='__main__')
mesh=json.loads((OUT/'forest-tree/manifest.json').read_text())
raw=(OUT/'cybr-tree.rgba16.bin').read_bytes()
reports.append({'id':'cybr-tree','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'provenance':{'source':mesh['source'],'treeIndex':mesh['treeIndex'],'displayMesh':'forest-tree/manifest.json','method':'Full reviewed mesh for display; porous foliage and wood collision/fuel proxy derived from that same mesh.'}})
(OUT/'manifest.json').write_text(json.dumps({'format':'rgba16float','channels':['distance','fuelCapacity','thermalResponse','material'],'models':reports},indent=2),encoding='utf-8')
print(json.dumps({'models':len(reports),'bytes':sum(x['bytes'] for x in reports),'output':str(OUT)}))
