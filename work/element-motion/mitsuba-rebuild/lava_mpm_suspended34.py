"""Suspended lava trail material: pressure-loaded shell without a floor.

Zero net gravity represents the external support of the bending shot. Melt
influx, internal stresses, fracture, heat transfer and motion are simulated.
Initial cooling is a mapped 1D history, not a claimed full emplacement solve.
"""
import numpy as np,hashlib
from pathlib import Path
import lava_mpm_scene33 as runner
from lava_mpm_scene32 import cooled_profile
from lava_mpm import MPM,Material,block,SOURCE_HASHES

def initial(source_interval=.1):
    spacing=.002;sample=np.full(3,spacing);cell=sample*2
    radius=np.array([.030,.015,.012]);center=np.array([0,0,.009]);plane=-.030
    # Match the material lattice used by incoming source columns in z.
    x=block([plane,-.015,-.004],[.030,.015,.022],sample)
    q=x-center;radial=np.linalg.norm(q/radius,axis=1)
    conduit=(x[:,0]<-.016)&(abs(x[:,1])<.007)&(x[:,2]>0)&(x[:,2]<.018)
    x=x[((radial<1)&(x[:,0]>=-.020))|conduit];q=x-center;radial=np.linalg.norm(q/radius,axis=1)
    grad=np.linalg.norm(q/radius**2,axis=1)/np.maximum(radial,1e-8)
    depth=(1-radial)/np.maximum(grad,1e-8)
    tube=np.minimum.reduce([.007-abs(x[:,1]),x[:,2],.018-x[:,2]])
    depth=np.maximum(depth,np.where(x[:,0]<-.016,tube,-1.))
    m=Material(rheology='basalt_power_creep',melt_viscosity_law='farrell_180719',fracture_length=2*spacing)
    z,temp,thermal=cooled_profile(m,age=180.)
    t=np.interp(np.maximum(depth,0),z,temp);blend=np.clip((-.014-x[:,0])/.014,0,1)
    t=m.temperature((1-blend)*m.enthalpy(t)+blend*m.enthalpy(1450.))
    config=dict(plane=plane,half_width=.007,height=.018,peak_speed=.008,temperature=1450.,pipe_end=-.020,bottom_wall=True,ground_profile=False)
    s=MPM(x,spacing,cell[0],temperature=t,material=m,origin=[-.050,-.05,-.047],shape=[40,27,32],gravity=(0,0,0),ground=False,cell_size=cell,sample_size=sample)
    setup=dict(sceneKind='suspended_continuous_crust_pressure_inlet',initialCondition='Continuous 6 x 3 x 2.4 cm lobe; no initial damage or cracks. No floor. Zero net gravity represents elemental support. A mapped 180-second cooling profile sets the initial shell temperature; prior cooling stress is not included.',thermalProfile=thermal,config=config,period=.1,nextEmission=.1,emissions=0,sourceHashes=SOURCE_HASHES,driverSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),limits='Nominal material model and coarse mechanism screen; no convergence or visual acceptance claim.')
    return s,setup,(z,temp)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--name',default='suspended-pressure');p.add_argument('--until',type=float,default=1.);p.add_argument('--wall',type=float,default=240);p.add_argument('--dt',type=float,default=.05);a=p.parse_args()
    runner.initial=initial;runner.run(a.name,a.until,a.wall,a.dt)
