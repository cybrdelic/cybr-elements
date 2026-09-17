"""Common camera and source timing, plus supported damped material motion.

The bending support is an authored external force. Release uses ballistic motion;
this retargeting rig does not claim to be a fresh FLIP or MPM solve.
"""
import numpy as np
DURATION=15;FPS=30;TOTAL=450;WRITE=6.827;RELEASE=11.
def smooth(x):
    x=np.clip(x,0,1);return x*x*(3-2*x)
def camera(data,t):
    x=np.interp(np.clip(t-.08,0,WRITE),data['times'],data['points'][:,0]);follow=np.clip(x,-2.2,2.2)
    z=smooth((t-5.55)/1.9)
    return follow*(1-z),6.4+5*z
def displaced(rest,born,t,kind,groups=None):
    age=np.maximum(0,t-born);amp={'metal':.045,'ice':.018,'glass':.012,'crystal':.014,'mud':.07,'blood':.055,'foam':.05,'lava':.04,'plants':.06,'healing':.05,'sand':.085,'snow':.055,'seismic':.012}.get(kind,.025)
    phase=rest[:,0]*4.7+rest[:,2]*6.3
    envelope=amp*np.exp(-age*3);envelope[envelope<.00012]=0
    wave=envelope*np.sin(age*11+phase)
    p=rest.copy();p[:,0]+=wave*.55;p[:,1]+=wave;p[:,2]+=wave*.7
    if kind in ['mud','blood','foam','lava']:
        w=.006 if kind=='lava' else .011
        p[:,1]+=w*np.sin(phase*1.5-t*3)*np.exp(-np.maximum(0,t-RELEASE))
    release=np.maximum(0,t-RELEASE)
    if release:
        delay=.08*(.5+.5*np.sin(phase));dt=np.maximum(0,release-delay)
        if groups is not None:
            ph=groups*.718;delay=.10*(.5+.5*np.sin(ph));dt=np.maximum(0,release-delay)
        else:ph=phase
        p[:,0]+=.12*np.sin(ph)*dt;p[:,1]+=.08*np.cos(ph)*dt
        p[:,2]-=.5*2.8*dt*dt
    return p
