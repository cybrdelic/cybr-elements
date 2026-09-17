"""Advected condensation tracer with curl forcing and pressure projection."""
from pathlib import Path
import numpy as np,torch,torch.nn.functional as F,cv2,math,json
torch.set_num_threads(2);torch.set_grad_enabled(False)
root=Path(__file__).parent;H,W=320,512;device='cuda'
z,x=torch.meshgrid(torch.linspace(0,5.8,H,device=device),torch.linspace(-5.25,5.25,W,device=device),indexing='ij')
grid=torch.stack([x/5.25,z/2.9-1],-1)[None];h=10.5/(W-1);dt=1/60
for variant in ['01','02']:
    a=np.load(root/f'brand-fire-{variant}.npz');mask=torch.tensor(a['supply'],device=device)[None,None];arrival=torch.tensor(a['arrival']/1.875,device=device)[None,None]
    edge=(mask-F.avg_pool2d(mask,9,1,4)).abs();source_shape=.20*mask+edge*2.5
    v=torch.zeros((1,2,H,W),device=device);d=torch.zeros((1,1,H,W),device=device)
    out=root/f'air-density-{variant}';out.mkdir(exist_ok=True)
    def adv(q):return F.grid_sample(q,grid-(v*torch.tensor([2/10.5,2/5.8],device=device)[None,:,None,None]*dt).permute(0,2,3,1),align_corners=True,padding_mode='zeros')
    for frame in range(450):
        for sub in range(2):
            t=(frame+sub/2)/30;pt=max(0,t*1.875-.08)
            cx=np.interp(pt,a['times'],a['points'][:,0]);cz=np.interp(pt,a['times'],a['points'][:,1])
            cx0=np.interp(pt-.02,a['times'],a['points'][:,0]);cz0=np.interp(pt-.02,a['times'],a['points'][:,1]);dx,dz=cx-cx0,cz-cz0;norm=max(1e-6,np.hypot(dx,dz));dx/=norm;dz/=norm
            v=adv(v);d=adv(d)
            curlx=.48*torch.sin(x*4+t*.8)*torch.cos(z*5-t*.7)+.24*torch.sin(x*9-z*7+t*2)
            curlz=-.384*torch.cos(x*4+t*.8)*torch.sin(z*5-t*.7)+.30*torch.sin(x*7+z*9-t*1.6)
            target=torch.stack([curlx+(.17 if t<11 else 1.25),curlz+.055])[None]
            v.lerp_(target,dt*1.7)
            nozzle=torch.exp(-((x-float(cx))**2+(z-float(cz))**2)/.018)[None,None]*(t<6.95)
            v[:,0:1].lerp_(torch.ones_like(d)*(-dx*2+.3),nozzle*.18);v[:,1:2].lerp_(torch.ones_like(d)*(-dz*2),nozzle*.18)
            div=(torch.roll(v[:,0:1],-1,3)-torch.roll(v[:,0:1],1,3)+torch.roll(v[:,1:2],-1,2)-torch.roll(v[:,1:2],1,2))/(2*h)
            p=torch.zeros_like(d)
            for _ in range(12):p=(torch.roll(p,1,2)+torch.roll(p,-1,2)+torch.roll(p,1,3)+torch.roll(p,-1,3)-div*h*h)*.25
            v[:,0:1]-=(torch.roll(p,-1,3)-torch.roll(p,1,3))/(2*h);v[:,1:2]-=(torch.roll(p,-1,2)-torch.roll(p,1,2))/(2*h)
            active=((t-arrival)/.25).clamp(0,1)*(t<11)
            d.add_((source_shape*active*2.0+nozzle*3)*dt)
            d.lerp_(F.avg_pool2d(d,3,1,1),.09);d.mul_(math.exp(-1.7*dt));d.clamp_(0,3)
        pixels=(d[0,0].flip(0).clamp(0,2)/2*65535).short().cpu().numpy().view('uint16')
        cv2.imwrite(str(out/f'{frame:04}.png'),pixels)
        if frame%90==0:print(json.dumps({'variant':variant,'frame':frame,'tracerMass':float(d.sum())}),flush=True)
