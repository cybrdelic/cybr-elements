"""Review camera exposure from the same CPU radiance cache; no rerender."""
import json,numpy as np
from PIL import Image,ImageDraw
from lava_mpm import ROOT
from cpu_oidn import denoise

def tonemap(x):
    x=np.maximum(x,0);x=np.clip(x*(2.51*x+.03)/(x*(2.43*x+.59)+.14),0,1)
    return np.where(x<=.0031308,12.92*x,1.055*x**(1/2.4)-.055)

folder=ROOT/'continuous-21'/'optical-proof';a=np.load(folder/'state-checkpoint.npz')
raw=a['color'];clean=denoise(raw,a['albedo'],a['normal']);clean[np.max(raw,axis=-1)==0]=0
sheet=Image.new('RGB',(1536,356));draw=ImageDraw.Draw(sheet)
for i,exposure in enumerate((.6,2.,6.)):
    picture=Image.fromarray((tonemap(clean*exposure)*255).astype('u1'));picture.save(folder/f'state-exposure-{exposure:g}.png')
    sheet.paste(picture.resize((512,320)),(512*i,36));draw.text((512*i+14,10),f'Camera exposure {exposure:g} | same radiance / no new rendering',fill='#aaa')
sheet.save(folder/'exposure-review.png');print(json.dumps(dict(contactSheet=str(folder/'exposure-review.png'),size=[1536,356],newRenderSamples=0)))
