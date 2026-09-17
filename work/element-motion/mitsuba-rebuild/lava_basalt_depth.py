"""Preserve the preferred basalt surface; improve its coarse volume only."""
import os,time,json,hashlib
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
import numpy as np
from lava_skin import normals
from lava_lobes_cpu import preview
from lava_breakout_cpu import smooth
R=Path(__file__).resolve().parent/'lava-focus'

def main():
    start=time.time();source=R/'refined-lobed-02.npz';a=dict(np.load(source));v=a['v'].astype('f8');f=a['f'];before=v.copy()
    # Keep every original crack, pore and irregular contour. This changes
    # only the large support shape, which was a broad, shallow oval.
    center=np.array([-.17,.02,0.]);v[:,0]=center[0]+(v[:,0]-center[0])*.88
    v[:,1]=center[1]+(v[:,1]-center[1])*.75
    upper=smooth((before[:,2]-.008)/.065)
    bulge=.10*np.exp(-((before[:,0]-.21)/.36)**2-((before[:,1]+.10)/.32)**2)
    bulge+=.045*np.exp(-((before[:,0]+.63)/.24)**2-((before[:,1]-.08)/.29)**2)
    v[:,2]+=upper*bulge
    # Coarse curvature continues beneath the rim instead of a flat cut
    # base. It is geometry on black, with no hidden display plinth.
    bottom=1-smooth((before[:,2]-.003)/.024)
    q=((before[:,0]+.17)/.94)**2+(before[:,1]/.69)**2
    v[:,2]-=bottom*.085*smooth(1-q)
    a.update(v=v.astype('f4'),normal=normals(v,f).astype('f4'),component=np.zeros(len(v),'u1'),camera_eye=np.array([.92,-2.18,1.28]),camera_target=np.array([-.17,0,.13]),camera_fov=np.array(35.))
    a['uv']=a['rest'][:,:2]*4
    path=R/'breakout/basalt-depth-01.npz';np.savez_compressed(path,**a);preview(a,path.with_name('basalt-depth-01-geometry.png'))
    report={'device':'CPU','source':str(source),'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'meshSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'seconds':round(time.time()-start,2),'method':'Original rough-basalt surface and temperature field preserved; coarse volume made thicker and less oval','limits':['Authored coarse deformation, not a new fluid solve','Existing temperature field remains authored from baseline crust exposure','No motion or sigil acceptance is claimed']}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':main()
