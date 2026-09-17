"""Fixed-scale CPU geometry and temperature review; no optical beautification."""
from pathlib import Path
import json,argparse
import numpy as np
from PIL import Image,ImageDraw
from lava_mpm_surface import extract
from lava_geometry_preview import raster
from lava_skin import normals


def sheet(paths,out,span=.032,center=(0,0,.004),labels=None):
    paths=[Path(p) for p in paths];w=360;h=270
    canvas=Image.new('RGB',(w*len(paths),h*2+45));draw=ImageDraw.Draw(canvas)
    forward=np.array([-.4,.75,-.52]);forward/=np.linalg.norm(forward)
    right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward)
    basis=np.array([right,up,forward]);center=np.array(center);report=[]
    for i,p in enumerate(paths):
        surface=extract(p);a=np.load(surface);v=a['v'];f=a['f'];q=(v-center)@basis.T
        screen=np.c_[w*.5+q[:,0]*w/span,h*.50-q[:,1]*w/span,q[:,2]+1.]
        if (screen[:,:2].min(0)<3).any() or (screen[:,:2].max(0)>[w-3,h-3]).any():
            raise ValueError('Fixed review camera clips the surface; increase span for the whole comparison')
        n=normals(v,f)[f].mean(1);shade=.17+.83*np.maximum(0,n@np.array([-.4,-.4,.8246]))
        gray=np.tile([.46,.47,.49],(len(f),1))*shade[:,None]
        hot=np.clip((a['temperature'][f].mean(1)-600)/850,0,1)
        thermal=np.c_[hot,hot**3*.65,hot**8*.15]
        for row,c in enumerate([gray,thermal]):
            rgb=(np.clip(c,0,1)**(1/2.2)*255).astype('u1');im=Image.fromarray(raster(screen,f,rgb,w,h));canvas.paste(im,(i*w,row*h+24))
        state=np.load(p);t=float(state['time']);draw.text((i*w+12,7),f'{t:.1f} s' if labels is None else labels[i],fill='#ddd')
        report.append(dict(path=str(p),time=t,broken=int(state['bond_broken'].sum()),maximumDamage=float(state['damage'].max())))
    draw.text((12,h*2+27),'CPU diagnostic. Fixed camera/scale. Gray geometry above; temperature below. No smoke or render relief.',fill='#bbb')
    canvas.save(out);Path(out).with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(image=str(out),frames=len(paths),size=list(canvas.size))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('paths',nargs='+',type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--span',type=float,default=.032);p.add_argument('--center',nargs=3,type=float,default=[0,0,.004]);p.add_argument('--labels',nargs='+');a=p.parse_args();sheet(a.paths,a.out,a.span,a.center,a.labels)
