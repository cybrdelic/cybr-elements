"""Checkpointed impact look development, reusing the verified pre-burst motion."""
import sys,json,shutil,argparse,time,gzip
from pathlib import Path
R=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--end',type=int,default=66);parser.add_argument('--finish',action='store_true');q=parser.parse_args()
code=(R/'reactive.py').read_text(encoding='utf-8').split('FPS=30')[0]
code=code.replace('blast=1.68<t<1.755','blast=1.68<t<1.77').replace('radius=.23 if blast else .085','radius=.34 if blast else .085').replace('(across/.18)**2+(y/.16)**2','(across/.24)**2+(y/.22)**2').replace('state[0,7]*7','state[0,7]*12')
code=code.replace('px/rr*7+float(dx)*12+shear*1.1','px/rr*14+float(dx)*2+shear*2.2').replace('y/rr*7+shear*1.1','y/rr*14+shear*2.2').replace('pz/rr*7+float(dz)*12+shear*1.1','pz/rr*14+float(dz)*2+shear*2.2')
sys.argv=['reactive.py','--name','checkpointed-combustion','--size','480','128','224','--fps','30','--substeps','8','--seconds','4','--warmup','0']
ns={'__file__':str(R/'reactive.py'),'__name__':'__burst_scene__'};exec(compile(code,str(R/'reactive.py'),'exec'),ns)
torch=ns['torch'];step=ns['step'];start=time.time();pre=R/'preburst-v2.pt.gz';current=R/'burst-state-v3.pt.gz'
if not pre.exists():
    for f in range(50):
        for sub in range(8):step((f+sub/8)/30)
        if f%15==0:print('PREBURST',f,round(time.time()-start,1),flush=True)
    with gzip.open(pre,'wb',compresslevel=1) as stream:torch.save({'state':ns['state'].cpu(),'nextFrame':50},stream)
checkpoint=current if q.finish and current.exists() else pre
with gzip.open(checkpoint,'rb') as stream:saved=torch.load(stream,map_location='cuda',weights_only=True)
ns['state'].copy_(saved['state']);first=int(saved['nextFrame']);del saved
out=R/'cache/combustion-burst';out.mkdir(parents=True,exist_ok=True)
for f in range(50):
    dest=out/f'{f:04}.npz'
    if not dest.exists():shutil.copyfile(R/'cache/combustion'/f'{f:04}.npz',dest)
import numpy as np,zipfile,io
end=120 if q.finish else q.end
for f in range(first,end):
    for sub in range(8):div=step((f+sub/8)/30)
    assert torch.isfinite(ns['state']).all()
    fields=ns['state'][0,[5,6,7]].cpu().numpy();fields[np.abs(fields)<.002]=0
    if f<66:assert fields[0].max()>.01,'Empty thermal checkpoint'
    buffer=io.BytesIO();np.save(buffer,fields.astype('<f2'))
    with zipfile.ZipFile(out/f'{f:04}.npz','w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:z.writestr('fields.npy',buffer.getbuffer())
    if f%5==0:print('BURST',f,round(time.time()-start,1),flush=True)
with gzip.open(current,'wb',compresslevel=1) as stream:torch.save({'state':ns['state'].cpu(),'nextFrame':end},stream)
(out/'report.json').write_text(json.dumps({'frames':end,'complete':end==120,'method':'checkpointed directional low-Mach reactive expansion','radius':.34,'burstDuration':.09,'source':'burst.py','limits':'No compressible shock propagation'},indent=2),encoding='utf-8');print('BURST PASS',end,flush=True)
