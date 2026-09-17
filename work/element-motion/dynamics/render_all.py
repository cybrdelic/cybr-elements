"""Render selected reviewed families, recording complete fresh frame receipts."""
from pathlib import Path
import subprocess,sys,json,time,hashlib
R=Path(__file__).resolve().parent;BLENDER='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
SCRIPTS={**dict.fromkeys(['sand','snow','metal'],'render_mpm.py'),**dict.fromkeys(['ice','glass','lava'],'render_phase.py'),**dict.fromkeys(['mud','blood'],'render_liquid.py'),**dict.fromkeys(['plants','healing'],'render_botanical.py'),**dict.fromkeys(['sound','pressure','flight','seismic','heat','energy','spirit'],'render_fields.py'),**dict.fromkeys(['lightning','lightning-redirection'],'discharge.py'),'foam':'render_foam.py','crystal':'render_crystal.py','spirit-projection':'projection.py'}
receipts=R/'receipts';receipts.mkdir(exist_ok=True)
SCRIPTS['glass']='render_glass.py'
SCRIPTS['seismic']='seismic.py'
failures=[]
for kind in sys.argv[1:]:
    if kind in ['sand','snow','metal']:
        preflight=subprocess.run([sys.executable,str(R/'motion_preflight.py'),kind])
        if preflight.returncode:
            failures.append(kind);continue
    script=R/SCRIPTS[kind];deps=[script,R/'scene.py',R.parent/'shared-trail.json'];digest=lambda:hashlib.sha256(b''.join(p.read_bytes() for p in deps)).hexdigest();before=digest();started=time.time();log=R/f'full-{kind}.log'
    with log.open('w',encoding='utf-8') as stream:
        result=subprocess.run([BLENDER,'--factory-startup','-b','-t','3','--python-exit-code','1','--python',str(script),'--','--kind',kind,'--full'],stdout=stream,stderr=subprocess.STDOUT)
    files=[R/'frames'/kind/f'{f:04}.jpg' for f in range(120)]
    fresh=all(p.exists() and p.stat().st_mtime>=started-1 for p in files)
    if result.returncode!=0 or not fresh or before!=digest():
        print('FAILED',kind,'exit',result.returncode,'fresh',fresh,'unchanged',before==digest(),flush=True)
        failures.append(kind)
        continue
    receipt={'id':kind,'frames':120,'sourceHash':before,'started':started,'seconds':round(time.time()-started,2),'fresh':True}
    (receipts/f'{kind}.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print('RENDERED',kind,receipt['seconds'],flush=True)
    p=subprocess.run([sys.executable,str(R/'encode.py'),kind]);print('ENCODE',kind,p.returncode,flush=True)
    if p.returncode:failures.append(kind)
if failures:
    print('Incomplete candidates:',', '.join(failures),flush=True)
    raise SystemExit(1)
