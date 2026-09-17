from pathlib import Path
import numpy as np
head='''"""Lowercase hand-printing: rounded, slightly irregular, separate letters."""
import numpy as np
MODE='handprint'
START=.08
curves=[]
def pen(start, segments):
    p=np.array(start,float);parts=[p[None]]
    for a,b,c in segments:
        a=np.array(a);b=np.array(b);c=np.array(c);u=np.linspace(0,1,160)[1:,None]
        parts.append((1-u)**3*p+3*(1-u)**2*u*a+3*(1-u)*u*u*b+u**3*c);p=c
    return np.vstack(parts)
offsets=[0,1.03,2.09,3.18,4.13,5.23,6.30,7.03,7.72]
def add(i,p):
    p=p.copy()
    # The variations are part of the handwriting, not animated letter deformation.
    p[:,0]+=[.035,-.025,.012,.025,-.01,.02,-.02,.015,.035][i]*p[:,1]
    p[:,0]+=.008*np.sin(p[:,1]*5+i)
    p[:,0]+=offsets[i]-4.30
    p[:,1]+=[0,.025,-.01,.035,.01,-.02,.015,.025,-.015][i]+1.20
    curves.append(p)
add(0,pen((.80,.82),[((.55,1.13),(.07,1.01),(.035,.53)),((-.025,.02),(.43,-.13),(.78,.16))]))
add(1,pen((.05,.98),[((.11,.73),(.26,.39),(.49,.26))]))
add(1,pen((.85,1.02),[((.71,.57),(.55,.12),(.39,-.36)),((.33,-.58),(.15,-.64),(.03,-.52))]))
add(2,pen((.12,1.48),[((.07,1.0),(.055,.43),(.06,.015))]))
add(2,pen((.07,.66),[((.27,1.11),(.83,1.08),(.84,.54)),((.88,.08),(.30,-.16),(.07,.17))]))
add(3,pen((.10,.015),[((.12,.35),(.13,.72),(.09,.98))]))
add(3,pen((.13,.64),[((.32,1.02),(.63,1.11),(.81,.88))]))
add(4,pen((.77,.84),[((.44,1.15),(.02,.88),(.035,.39)),((.06,-.16),(.63,-.10),(.77,.40))]))
add(4,pen((.82,1.49),[((.76,.97),(.80,.40),(.80,.015))]))
add(5,pen((.07,.48),[((.30,.48),(.57,.50),(.81,.56)),((.75,1.17),(.14,1.12),(.055,.65)),((-.095,.03),(.48,-.13),(.83,.12))]))
add(6,pen((.18,1.47),[((.13,1.02),(.095,.52),(.11,.18)),((.11,.025),(.24,-.01),(.45,.055))]))
add(7,pen((.22,.94),[((.19,.67),(.17,.30),(.19,.04))]))
add(7,pen((.20,1.26),[((.21,1.29),(.25,1.29),(.25,1.25)),((.25,1.21),(.20,1.21),(.20,1.26))]))
add(8,pen((.82,.84),[((.56,1.10),(.08,1.02),(.055,.54)),((-.025,.04),(.46,-.12),(.83,.16))]))
'''
tail=Path('work/sans_motion.py').read_text().split('# Keep a single moving source.')[1]
Path('work/handprint_motion.py').write_text(head+'\n# Keep a single moving source.'+tail)
import sys;sys.path.insert(0,'work')
import handprint_motion as m
from PIL import Image,ImageDraw
im=Image.new('RGB',(1500,500),'#121212');d=ImageDraw.Draw(im)
for p in m.curves:d.line([(750+x*145,435-z*135) for x,z in p],fill='#f2cf9c',width=5)
im.save('work/handprint-proof.jpg',quality=94)
print({'strokes':len(m.curves),'writingDuration':m.WRITE,'proof':'work/handprint-proof.jpg'})
