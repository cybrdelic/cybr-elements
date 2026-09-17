import json,numpy as np
from pathlib import Path
DATA=json.loads((Path(__file__).parent/'shared-trail.json').read_text());MODE='arc';START=DATA['start'];WRITE=DATA['write'];A=DATA['frames']
def sample(t):
 q=np.clip(t*DATA['sampleRate'],0,len(A)-1);i=int(q);j=min(i+1,len(A)-1);return A[i],A[j],q-i
def pose(t):
 a,b,u=sample(t);p=np.array(a['p'])*(1-u)+np.array(b['p'])*u;d=np.array(a['d'])*(1-u)+np.array(b['d'])*u;d/=max(1e-8,np.linalg.norm(d));return p,d,a['on']*(1-u)+b['on']*u,a['speed']*(1-u)+b['speed']*u
def turn_rate(t):
 a,b,u=sample(t);return a['turn']*(1-u)+b['turn']*u
