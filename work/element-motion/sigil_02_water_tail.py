"""Frustum-cull reconstruction after liquid exits, retaining native simulation."""
from pathlib import Path
import time,sys
R=Path(__file__).resolve().parent;O=R/'sigil-02-elements';source=O/'water-particles'
while not list(source.glob('*.gz')):time.sleep(.3)
first=min(int(p.stem) for p in source.glob('*.gz'))
s=(R/'sigil_02_water_mesh.py').read_text()
s=s.replace('full=True;frames=range(294)',f'full=True;frames=range({first},294)')
s=s.replace("p=raw[:n*3].reshape(-1,3);v=raw[n*3:].reshape(-1,3);extent=", "p=raw[:n*3].reshape(-1,3);v=raw[n*3:].reshape(-1,3);keep=p[:,1]>.56;p=p[keep];v=v[keep];n=len(p);isolated=np.empty(0,bool);spray=None;extent=")
s=s.replace('if n>4:', 'if n>2048:').replace("if n>4 and abs", "if n>2048 and abs")
s=s.replace('verts=normals=drops=vv=dv=np.empty((0,3),np.float32);faces=np.empty((0,3),np.uint32);radii=np.empty(0,np.float32);measure={}',"verts=normals=vv=np.empty((0,3),np.float32);faces=np.empty((0,3),np.uint32);drops=p.copy();dv=v.copy();radii=np.full(n,np.cbrt((h*.5)**3*3/(4*np.pi)),np.float32);measure={'frustumTailParcels':n,'representedVolume':float(n*(h*.5)**3),'totalRepresentedVolumeError':0.0}")
# solverY=.56 corresponds to worldZ=-1.20, below the bottom of the camera.
# The full particle simulation continues, including the unseen floor impact.
print('FRUSTUM RECONSTRUCTION START',first,flush=True)
exec(compile(s,str(R/'sigil_02_water_mesh.py'),'exec'),{'__file__':str(R/'sigil_02_water_mesh.py'),'__name__':'__main__'})
