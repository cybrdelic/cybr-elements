from pathlib import Path
import gzip,struct
import numpy as np
R=Path(__file__).resolve().parent
O=R.parents[2]/'outputs/cybrdelic-type/elements/motion'

def fluid_particles(frame,viscous=False):
    p=R.parent/('viscous-cache' if viscous else 'water-shared-cache')/f'{frame:04}.gz'
    raw=gzip.decompress(p.read_bytes());n=len(raw)//24;a=np.frombuffer(raw,'<f4').reshape(2,n,3)
    def co(v):return np.column_stack([v[:,0]/.4-5.25,(v[:,2]-.9)/.4,v[:,1]/.4])
    def vel(v):return np.column_stack([v[:,0]/.4,v[:,2]/.4,v[:,1]/.4])
    return co(a[0]),vel(a[1])

def fluid_mesh(frame,viscous=False):
    folder=O/'water/cache'/('viscous' if viscous else 'material')
    files=list(folder.glob(f'{frame:04}.*'))
    if not files:
        files=list(folder.glob(f'*{frame:04}*'))
    p=next(x for x in files if x.suffix in ['.gz','.bin'])
    raw=p.read_bytes()
    if raw[:2]==b'\x1f\x8b':raw=gzip.decompress(raw)
    nv,nf,nd=struct.unpack_from('<III',raw,4);off=32
    v=np.frombuffer(raw,'<u2',nv*3,off).reshape(-1,3).astype('f4')/65535*np.array([4.2,2.4,1.8]);off+=nv*6+nv*6+nv
    faces=np.frombuffer(raw,'<u4',nf*3,off).reshape(-1,3)[:,[0,2,1]];off+=nf*12
    drops=np.frombuffer(raw,'<u2',nd*3,off).reshape(-1,3).astype('f4')/65535*np.array([4.2,2.4,1.8]);off+=nd*6
    rad=np.frombuffer(raw,'<f4',nd,off)/.4
    def co(v):return np.column_stack([v[:,0]/.4-5.25,(v[:,2]-.9)/.4,v[:,1]/.4])
    return co(v),faces,co(drops),rad
