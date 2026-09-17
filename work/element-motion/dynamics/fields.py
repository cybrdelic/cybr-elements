"""Distinct, integrated tracer mechanisms on the common emitter trajectory.
These visualize authored bending fields, not calibrated acoustic/EM phenomena.
"""
import sys,json,time
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R.parent));from shared_motion import pose,turn_rate

def run(kind):
    rng=np.random.default_rng(194);N=18000 if kind in ['flight','pressure','sound'] else 7500
    birth=np.sort(rng.uniform(.08,1.68,N));p=np.zeros((N,3));d=np.zeros_like(p)
    tt=np.linspace(.08,1.68,2000);pd=np.array([pose(float(t))[0] for t in tt]);dd=np.array([pose(float(t))[1] for t in tt])
    p[:,0]=np.interp(birth,tt,pd[:,0]);p[:,2]=np.interp(birth,tt,pd[:,1]);d[:,0]=np.interp(birth,tt,dd[:,0]);d[:,2]=np.interp(birth,tt,dd[:,1]);normal=np.column_stack([-d[:,2],np.zeros(N),d[:,0]])
    width={'flight':.10,'pressure':.25,'sound':.16,'heat':.07,'energy':.075,'spirit':.10,'seismic':.19}[kind]
    off=rng.normal(0,width,(N,3));off[:,1]*=.7;p+=off;rest=p.copy();v=d*(6.9 if kind=='flight' else .8)
    history=[];brightness=[];radii=np.clip(.0015/np.maximum(rng.random(N),.018)**.42,.0015,.008)
    temperature=np.full(N,1350.);temperatures=[]
    if kind=='seismic':radii*=3
    tags=rng.integers(0,2,N);phase=rng.random(N)*np.pi*2
    for frame in range(120):
        for sub in range(8):
            dt=1/240;t=(frame+sub/8)/30;age=np.maximum(0,t-birth);active=birth<=t
            # Guiding stops with the emitter, residual momentum is integrated.
            q,qd,on,_=pose(t);center=np.array([q[0],0,q[1]]);tangent=np.array([qd[0],0,qd[1]]);no=np.array([-qd[1],0,qd[0]])
            delta=p-center;rr=np.sum(delta**2,axis=1)
            force=np.zeros_like(p);drag=1.0
            if kind=='flight':
                for sign in [-1,1]:
                    qv=delta-no*sign*.16;r2=np.sum(qv**2,axis=1)+.025
                    swirl=np.cross(np.tile(tangent,(N,1)),qv)*(sign*.65*np.exp(-r2/1.3)/r2)[:,None]
                    force+=swirl*on
                force+=d*(.7*np.exp(-age))[:,None];drag=3.5
            elif kind=='pressure':
                contraction=7*np.exp(-((age-.3)/.23)**2)-4*np.exp(-((age-.72)/.22)**2)
                force=-(p-rest)*14-off*contraction[:,None];drag=3.2
            elif kind=='sound':
                # Damped driven oscillators reveal passing compression pulses.
                driving=np.sin(age*28-phase*.04)*np.exp(-age*1.3)
                force=-(p-rest)*210+d*(driving*35)[:,None];drag=3.7
            elif kind=='seismic':
                driving=np.sin(age*22)*np.exp(-age*2.2);force=-(p-rest)*160+np.array([0,0,1])[None]*(driving*9)[:,None];drag=4.2
            elif kind=='heat':
                force=np.column_stack([.2*np.sin(p[:,2]*9+t*4),.15*np.cos(p[:,0]*11-t*3),np.exp(-age)*1.2]);drag=1.5
            else:
                swirlphase=birth*30+age*8+tags*np.pi
                target=normal*(np.cos(swirlphase)*.08)[:,None]+np.array([0,1,0])[None]*(np.sin(swirlphase)*.08)[:,None]
                if kind=='spirit':target*=np.exp(-age[:,None]*1.7)
                force=-(p-rest-target)*35+d*(1.8*np.exp(-age))[:,None];drag=3.0
            v[active]+=force[active]*dt;v[active]*=np.exp(-dt*drag);p[active]+=v[active]*dt
            if kind=='flight' and t<1.68:
                angle=float(np.clip(turn_rate(t),-25,25))*.3*dt*np.exp(-age*4);ca=np.cos(angle);sa=np.sin(angle);oldx=v[:,0].copy();v[:,0]=oldx*ca-v[:,2]*sa;v[:,2]=oldx*sa+v[:,2]*ca
            if kind=='heat':
                ratio=3/(7800*radii*500);loss=ratio*(150*(temperature-293)+.8*5.670374419e-8*(temperature**4-293**4));temperature[active]-=loss[active]*dt
        active=birth<=t;shown=p.copy();shown[~active,2]=-30
        energy=np.exp(-age*(1.2 if kind=='heat' else .55 if kind in ['flight','spirit'] else .25));energy[~active]=0
        if kind=='energy':energy*=.25+.75*np.exp(-((age%(.46))/.14)**2)
        if kind=='sound':energy*=.3+.7*(.5+.5*np.cos(age*28))**4
        if kind=='pressure':energy*=.35+.65*np.exp(-((age-.32)/.2)**2)
        if kind=='seismic':energy*=.4+.6*np.exp(-age*2)
        history.append(shown.astype('f4'));brightness.append(energy.astype('f4'))
        temperatures.append(temperature.astype('f4').copy())
    out=R/'cache'/kind;out.mkdir(parents=True,exist_ok=True);np.savez_compressed(out/'tracers.npz',p=history,energy=brightness,r=radii.astype('f4'),tag=tags,birth=birth.astype('f4'),rest=rest.astype('f4'),temperature=temperatures)
    (out/'report.json').write_text(json.dumps({'kind':kind,'frames':120,'particles':N,'solver':'8-substep integrated tracers','mechanism':{'flight':'counter-rotating vortex pair','pressure':'contraction and rebound','sound':'traveling driven pressure oscillation','seismic':'elastic displacement response','heat':'cooling buoyant tracers','energy':'coupled helical channels with pulses','spirit':'relaxation from disordered to coherent channels'}[kind],'limits':'Art-directed field visualization; no claim of physical magic or calibrated acoustics'},indent=2),encoding='utf-8');print(kind,'120 frames',flush=True)
for k in sys.argv[1:] or ['sound','pressure','flight','seismic','heat','energy','spirit']:run(k)
