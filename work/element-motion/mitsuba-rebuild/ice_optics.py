"""Closed air cavities driven by freezing and broken solid bonds.

The closed outer surface, air/ice interfaces and cold-air volume are separate
optical objects. This avoids painting white cracks onto a transparent tube.
"""
from pathlib import Path
import json,numpy as np
from scipy.spatial import cKDTree

def add_cavities(scene,mi,root,frame,surface,write_ply):
 import trimesh
 unit=trimesh.creation.icosphere(subdivisions=2);unit_v=np.array(unit.vertices);unit_f=np.array(unit.faces);geo=root/'renders/ice/geometry';geo.mkdir(parents=True,exist_ok=True)
 def ellipsoid(name,center,scale,rotation=None):
  rotation=np.eye(3) if rotation is None else rotation;vertices=(unit_v*np.array(scale))@rotation.T+center;normals=(unit_v/np.array(scale))@rotation.T;normals/=np.linalg.norm(normals,axis=1)[:,None];path=geo/f'{name}-{frame:04}.ply';write_ply(path,vertices,unit_f,normals,unit_v[:,:2]);return {'type':'ply','filename':str(path)}
 T=mi.ScalarTransform4f;a=np.load(root/'cache/ice'/f'{frame:04}.npz');p=a['p'];tree=cKDTree(surface);rng=np.random.default_rng(419)
 interface={'type':'dielectric','int_ior':1.000277,'ext_ior':1.31};medium={'type':'ref','id':'ice_medium'};frozen=np.flatnonzero(a['phase']>.9);bubbles=0;cracks=0
 # Bubbles are trapped only in frozen material. Their mostly microscopic
 # size distribution is bounded to avoid the old oversized bead problem.
 if len(frozen):
  candidates=rng.choice(frozen,min(len(frozen),380),replace=False);radii=np.minimum(.0035,.00038*(1+rng.pareto(2.2,len(candidates))));distance,_=tree.query(p[candidates]);valid=distance>radii*3
  for q,(ix,rad) in enumerate(zip(candidates[valid],radii[valid])):
   scene[f'trapped_air_{q}']={**ellipsoid(f'bubble-{q}',p[ix],[rad,rad*.72,rad*1.25]),'bsdf':interface,'exterior':medium};bubbles+=1
 source=root/'cache/ice'/f'bonds-{frame:04}.npz'
 if source.exists():
  b=np.load(source);sel=np.flatnonzero((b['status']==2)&(b['pairs'].max(1)<len(p)));pairs=b['pairs'][sel];mid=p[pairs].mean(1) if len(pairs) else np.empty((0,3));distance,_=tree.query(mid);order=np.argsort(-b['peakStrain'][sel]);used=set()
  for j in order:
   cell=tuple(np.floor(mid[j]/.075).astype(int))
   if cell in used or distance[j]<.013:continue
   used.add(cell);i0,i1=pairs[j];normal=p[i1]-p[i0];normal/=max(float(np.linalg.norm(normal)),1e-8);center=mid[j];radius=min(float(distance[j])*.64,.045);gap=float(np.clip(b['peakStrain'][sel[j]]*b['restLength'][sel[j]]*.1,2e-5,.0004));up=[0,0,1] if abs(normal[2])<.85 else [0,1,0]
   rotation=np.asarray(T().look_at(origin=center,target=center+normal,up=up).matrix)[:3,:3]
   scene[f'fracture_air_{cracks}']={**ellipsoid(f'crack-{cracks}',center,[radius,radius*.63,gap],rotation),'bsdf':{'type':'roughdielectric','distribution':'ggx','alpha':.018,'int_ior':1.000277,'ext_ior':1.31},'exterior':medium};cracks+=1
   if cracks>=100:break
 report={'trappedBubbles':bubbles,'resolvedOpticalCracks':cracks,'note':'Air cavity placement is driven by phase and irreversible broken bonds. Closed oblate cavities approximate fracture faces; crack-tip growth is not resolved.'};out=root/'renders/ice';out.mkdir(parents=True,exist_ok=True);(out/f'optics-{frame:04}.json').write_text(json.dumps(report,indent=2));return report
