import gzip,json
from pathlib import Path
import numpy as np
from PIL import Image
base=Path(r'C:\Users\alexf\Documents\Codex\2026-09-04\re\work\cybrdelic.github.io\assets\gallery\spatial')
info=json.loads((base/'flame-native-emitter/index.json').read_text())
out=Path(__file__).resolve().parent/'native-flame';out.mkdir(exist_ok=True)
shape=tuple(info['dimensions'][::-1]);dy=info['extent'][1]/(shape[1]-1)
for i in range(24):
    row=info['frames'][i*2]
    raw=np.frombuffer(gzip.decompress((base/row['file']).read_bytes()),np.uint8).reshape(*shape,4)
    linear=(raw.astype(np.float32)/255)**2*16
    sigma=linear[...,3]
    atten=np.exp(-sigma*dy)
    trans=np.concatenate([np.ones_like(atten[:,:1]),np.cumprod(atten[:,:-1],axis=1)],axis=1)
    image=(trans[...,None]*linear[...,:3]*(1-atten[...,None])/np.maximum(sigma[...,None],1e-6)).sum(axis=1)[::-1].copy()
    np.save(out/f'{i:03d}.npy',image.astype(np.float16))
    if i in [0,12]:
        im=image*.6
        im=np.clip((im*(2.51*im+.03))/(im*(2.43*im+.59)+.14),0,1)
        im=np.where(im<=.0031308,im*12.92,1.055*im**(1/2.4)-.055)
        Image.fromarray((im*255).astype(np.uint8)).resize((792,960)).save(out/f'{i:03d}.jpg')
print(json.dumps({'frames':24,'source':'flame-native-emitter','folder':str(out)}))
