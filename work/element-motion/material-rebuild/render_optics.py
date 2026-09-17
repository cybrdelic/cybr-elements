"""Resolved black-field phase optics from pressure and temperature.

Off-axis optical illumination is rejected at the camera; only deflected light
reaches it. These remain amplified slow-motion optical studies, not a claim
that unlit pressure or heat is visible against black to the naked eye.
"""
from pathlib import Path
import sys,numpy as np,json
from scipy.ndimage import zoom,gaussian_filter
from PIL import Image
R=Path(__file__).resolve().parent;D=R.parent/'dynamics';sys.path.insert(0,str(R.parent));from shared_motion import pose
K=sys.argv[sys.argv.index('--kind')+1];selected=list(range(120)) if '--full' in sys.argv else list(map(int,sys.argv[sys.argv.index('--frames')+1].split(',')))
X,Z=960,540;x=np.linspace(-5.25,5.25,X,dtype='f4')[None];z=np.linspace(-1.05,4.85625,Z,dtype='f4')[:,None];out=R/'frames'/K;out.mkdir(parents=True,exist_ok=True)
fx=np.fft.fftfreq(X);fz=np.fft.fftfreq(Z);freq=fz[:,None]**2+fx[None]**2
events=np.arange(.10,1.69,.14 if K=='sound' else .40);centers=[pose(float(t))[0] for t in events]
quadrature,weights=np.polynomial.legendre.leggauss(48)
def projected_shell(radial,radius,width):
 # Adaptive Abel quadrature only traverses the shell. Uniform depth samples
 # undersampled narrow waves and produced false concentric rings.
 lower=np.sqrt(np.maximum(0,max(0,radius-6*width)**2-radial));upper=np.sqrt(np.maximum(0,(radius+6*width)**2-radial));half=(upper-lower)*.5;middle=(upper+lower)*.5;value=np.zeros_like(radial)
 for node,weight in zip(quadrature,weights):
  y=middle+half*node;u=(np.sqrt(radial+y*y)-radius)/width;value+=weight*u*np.exp(-.5*u*u)
 return value*(upper-lower)
for f in selected:
 t=(f+1)/30
 if K=='heat':
  temp=np.load(D/'cache/combustion'/f'{f:04}.npz')['fields'][0].astype('f4');path=(.00027*(293/(293+500*np.maximum(0,temp))-1)).sum(1)*(3/(temp.shape[1]-1));path=zoom(path,(384/path.shape[0],X/path.shape[1]),order=3);full=np.zeros((Z,X),dtype='f4');full[96:480]=path;path=gaussian_filter(full,.45)
 else:
  path=np.zeros((Z,X),dtype='f4')
  for event,center in zip(events,centers):
   age=t-event
   if age<=0 or age>1.35:continue
   radius=(1.55*age if K=='sound' else .62*max(0,1-age/.42)**1.5+2.3*max(0,age-.42));width=(.025 if K=='sound' else .060)+age*.007
   radial=(x-center[0])**2+(z-center[1])**2;atten=np.exp(-age*(3.0 if K=='sound' else 2.0))/(radius+.25)
   # Integrate the actual 3-D bipolar shell through camera depth. The narrow
   # optical wavefront derives from index gradients rather than a painted ring.
   pulse=projected_shell(radial,radius,width)
   if K=='pressure':pulse=-pulse+.55*projected_shell(radial,radius*.63,width)
   path+=pulse*atten*.00008
 gz,gx=np.gradient(path);sensitivity=36000 if K=='heat' else 92000
 phase=np.pad(path*sensitivity*(1.6 if K=='pressure' else 1),128)
 fz=np.fft.fftfreq(phase.shape[0]);fx=np.fft.fftfreq(phase.shape[1]);freq=fz[:,None]**2+fx[None]**2
 wave=np.exp(1j*phase);spectrum=np.fft.fft2(wave);rgb=[]
 for dispersion in [.995,1,1.005]:
  diffracted=np.fft.ifft2(spectrum*np.exp(-1j*np.pi*freq*5.5*dispersion))
  signal=np.abs(diffracted-wave)[128:-128,128:-128]**2*48
  signal+=(np.maximum(0,gx*.65+gz*.35)*sensitivity)**1.5*.07
  rgb.append(1-np.exp(-signal))
 image=np.stack(rgb,-1);image=np.clip(image,0,1)**.60
 image=Image.fromarray(np.uint8(image[::-1]*255)).resize((1920,1080),Image.Resampling.LANCZOS);image.save(out/f'{f:04}.jpg',quality=97)
 print('OPTICS',K,f,flush=True)
(R/f'{K}-optics.json').write_text(json.dumps({'method':__doc__,'resolution':[X,Z],'frames':selected},indent=2))
