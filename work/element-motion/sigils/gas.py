"""Retarget the existing 3D gas-line solver to the unchanged brand sources.

The gas families share advection but have separate thermal/scattering diagnostics.
Steam is an effective condensate visualization, not a multiphase droplet solve.
"""
from pathlib import Path
import os,sys,argparse,json,time,gzip
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parent;WORK=R.parents[1];sys.path.insert(0,str(WORK));sys.path.insert(0,str(R))
from motion import camera
p=argparse.ArgumentParser();p.add_argument('--variant',required=True);p.add_argument('--until',type=int,default=450);p.add_argument('--resume',action='store_true');p.add_argument('--look',action='store_true');q=p.parse_args()
os.environ['BRAND_VARIANT']=q.variant
(R/'gas-work'/q.variant).mkdir(parents=True,exist_ok=True)
source=WORK/'render_brand_fire.py';code=source.read_text(encoding='utf-8').split('import subprocess\nimport sys\nFPS=30')[0]
code=code.replace("out = ROOT/f'brand-fire-{VARIANT}-frames'",f"out = Path({str(R/'gas-work'/q.variant)!r})")
sys.argv=[str(source),'--name','sigil-gas-'+q.variant,'--size','512','64','320','--fps','16','--substeps','5','--seconds','15','--warmup','0']
ns={'__file__':str(source),'__name__':'sigil_gas_solver'};exec(compile(code,str(source),'exec'),ns)
torch=ns['torch'];F=ns['F'];step=ns['step'];device=ns['device'];h=ns['h'];data=np.load(R/f'source-{q.variant}.npz')
checkpoint=R/f'gas-{q.variant}.pt.gz';first=0
if q.resume or q.look:
    with gzip.open(checkpoint,'rb') as stream:saved=torch.load(stream,map_location='cuda',weights_only=True)
    ns['state'].copy_(saved['state']);ns['reservoir'].copy_(saved['reservoir']);first=int(saved['nextFrame']);del saved
kinds=['blue-fire','combustion','steam','smoke','heat']
for k in kinds:(R/'frames'/f'{k}-{q.variant}').mkdir(parents=True,exist_ok=True)
start=time.time();H,W=1080,1920
def project(den,source):
    alpha=1-torch.exp(-den*h[1]);trans=torch.cat([torch.ones_like(alpha[:,:1]),torch.cumprod(1-alpha[:,:-1],dim=1)],dim=1)
    return (trans[...,None]*source*(alpha/den.clamp_min(1e-6))[...,None]).sum(1)
for f in ([first-1] if q.look else range(first,q.until)):
    if not q.look:
        for sub in range(5):step((f+sub/5)/16)
    state=ns['state'];assert torch.isfinite(state).all()
    temp=state[0,5];soot=state[0,6];reaction=state[0,7];hot=((temp-.35)/1.65).clamp(0,1);supply=ns['reservoir']
    t=f/30;cx,width=camera(data,t);height=width*9/16
    z,x=torch.meshgrid(torch.linspace(2.35+height/2,2.35-height/2,H,device=device),torch.linspace(cx-width/2,cx+width/2,W,device=device),indexing='ij')
    lookup=torch.stack([(x+5.25)/10.5*2-1,z/5.8*2-1],-1)[None]
    illumination=torch.exp(-torch.flip(torch.cumsum(torch.flip(soot,[0]),0),[0])*float(h[2])*2.8)
    for kind in kinds:
        if kind in ['blue-fire','combustion']:
            den=soot*3.6+reaction*.08
            if kind=='blue-fire':col=torch.stack([.08+.32*hot**3,.16+.58*hot**2,torch.ones_like(hot)],-1);power=reaction.pow(.85)*10
            else:
                col=torch.stack([torch.ones_like(hot),.045+.78*hot**1.15,.002+.25*hot**4],-1)
                burst=1+3*np.exp(-((t-11.08)/.15)**2);power=reaction.pow(.85)*10*burst
            linear=project(den,col*power[...,None])
        elif kind=='heat':
            thermal=temp*.035+supply*2
            optical=(-.00027*(500*thermal)/(293+500*thermal)).sum(1)*float(h[1]);gz,gx=torch.gradient(optical,spacing=(float(h[2]),float(h[0])))
            signal=1-torch.exp(-torch.sqrt(gx*gx+gz*gz)*1300);linear=signal[...,None]*torch.tensor([.30,.44,.52],device=device)
        else:
            if kind=='steam':den=soot*2+reaction*.55;gain=6.;color=[.74,.84,.92]
            elif kind=='smoke':den=soot*3.8+reaction*.12;gain=3.2;color=[.43,.46,.49]
            else:
                den=soot*.40+reaction*.20;gain=9.;color=[.48,.64,.74]
            scattering=illumination*.72+.12
            linear=project(den,den[...,None]*scattering[...,None]*torch.tensor(color,device=device)*gain)
        linear=F.grid_sample(linear.permute(2,0,1)[None],lookup,mode='bicubic',padding_mode='zeros',align_corners=True).clamp_min(0)
        if kind in ['blue-fire','combustion']:
            glow=F.avg_pool2d(F.avg_pool2d(linear,(1,17),1,(0,8)),(17,1),1,(8,0));linear=(linear+glow*.12)*.85
        mapped=(linear*(2.51*linear+.03)/(linear*(2.43*linear+.59)+.14)).clamp(0,1)
        mapped=torch.where(mapped<=.0031308,mapped*12.92,1.055*mapped.pow(1/2.4)-.055)
        image=(mapped[0].permute(1,2,0)*255).byte().cpu().numpy()
        folder=R/'look'/f'{kind}-{q.variant}' if q.look else R/'frames'/f'{kind}-{q.variant}';folder.mkdir(parents=True,exist_ok=True)
        Image.fromarray(image).save(folder/f'{f:04}.jpg',quality=97)
        del linear,mapped
    if f%30==0:print('GAS',q.variant,f,round(time.time()-start,1),flush=True)
if q.look:raise SystemExit(0)
with gzip.open(checkpoint,'wb',compresslevel=1) as stream:torch.save({'state':ns['state'].cpu(),'reservoir':ns['reservoir'].cpu(),'nextFrame':q.until},stream)
(R/f'gas-{q.variant}.json').write_text(json.dumps({'frames':q.until,'size':[512,64,320],'kinds':kinds,'complete':q.until==450,'seconds':time.time()-start,'model':'Existing 3D gas-line advection, reaction, cooling and finite reservoir release; separate optical field views'},indent=2),encoding='utf-8')
print('GAS COMPLETE',q.variant,q.until,flush=True)
