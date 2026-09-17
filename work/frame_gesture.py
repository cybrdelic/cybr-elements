from pathlib import Path
p=Path('work/render_gesture.py');s=p.read_text()
a=s.index('    # Upsample the volume integration in linear light, then optical glow.',s.index('def render(frame):'))
b=s.index('    encoder.stdin.write',a)
s=s[:a]+'''    # A steady travelling camera frames the rolling wake. The fluid itself is untouched.
    physical=frame/SIM_FPS
    camera_x=float(np.mean([nozzle_pose(physical+lag)[0][0] for lag in np.linspace(-1.2,.35,18)]))
    view_x=torch.linspace(camera_x-3.2,camera_x+3.2,W,device=device)
    view_z=torch.linspace(3.6,0,H,device=device)
    vz,vx=torch.meshgrid(view_z,view_x,indexing='ij')
    lookup=torch.stack([(vx+5.25)/10.5*2-1,vz/4.2*2-1],dim=-1)[None]
    linear=F.grid_sample(linear.permute(2,0,1)[None],lookup,mode='bicubic',padding_mode='zeros',align_corners=True).clamp_min(0)
    blur=F.avg_pool2d(F.avg_pool2d(linear,(1,21),stride=1,padding=(0,10)),(21,1),stride=1,padding=(10,0))
    linear=(linear+blur*.22)*.72
    im=((linear*(2.51*linear+.03))/(linear*(2.43*linear+.59)+.14)).clamp(0,1)
    im=torch.where(im<=.0031308,im*12.92,1.055*im.pow(1/2.4)-.055)
    edge_x=((5.25-vx.abs())/.45).clamp(0,1)
    edge_z=torch.minimum((3.6-vz)/.45,vz/.12).clamp(0,1)
    edges=edge_x*edge_x*(3-2*edge_x)*edge_z*edge_z*(3-2*edge_z)
    closing=min(1,max(0,(TOTAL-1-frame)/(FPS*.6)))
    pixels=(im[0].permute(1,2,0)*edges[:,:,None]*closing*255).byte().cpu().numpy()
''' +s[b:]
s=s.replace("ROOT/'gesture-preview-frames'","ROOT/'gesture-final-frames'")
s=s.replace("'no trail fitting, morph or cached particles.'","'no trail fitting, morph or cached particles.'")
p.write_text(s)
# Camera-only check from the actual preview frame; no simulation changes.
from PIL import Image
import numpy as np,sys
sys.path.insert(0,'work')
from gesture_motion import pose
im=Image.open('work/gesture-preview-frames/0090.jpg')
cam=np.mean([pose(3+lag)[0][0] for lag in np.linspace(-1.2,.35,18)])
left=(cam-3.2+5.25)/10.5*1280;right=(cam+3.2+5.25)/10.5*1280
im=im.crop((left,80+(4.2-3.6)/4.2*512,right,80+512)).resize((1280,720),Image.Resampling.LANCZOS)
im.save('work/gesture-framing-check.jpg',quality=93)
print('Travelling camera frames the native fluid wake; no field deformation.')
