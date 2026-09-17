"""Restoration of the original sigil, with actual closing cuts."""
from pathlib import Path
import sys,bpy,numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from common import *
s=setup();s.view_settings.exposure=-.35
body=scene.material('Restored mineral ceramic',(.065,.095,.075),.38,metal=.12);p=body.node_tree.nodes['Principled BSDF'];p.inputs['Subsurface Weight'].default_value=.045;no=noise(body,90,3);bump(body,no.outputs['Fac'],.0005,.16)
front=scene.emission('Localized healing interface',(.10,.80,.40),4);scene.glare(s,1.6,-.96)
for f in selected():
 a=np.load(R/'cpu/identity'/f'healing-{f:04}.npz');ob=mesh('Damaged original identity',a['v'],a['f'],body,smooth=False);be=ob.modifiers.new('Ceramic edge highlight','BEVEL');be.width=.0012;be.segments=2
 if len(a['front_v']):mesh('Moving repair interface',a['front_v'],a['front_f'],front,smooth=False)
 finish(s,'healing',f)
