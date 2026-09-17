"""Finish the reviewed burst cache, relight all frames, and record fresh proof."""
from pathlib import Path
import subprocess,sys,time,json,hashlib
R=Path(__file__).resolve().parent
with (R/'burst-finish.log').open('w',encoding='utf-8') as log:
    p=subprocess.run([sys.executable,str(R/'burst.py'),'--finish'],stdout=log,stderr=subprocess.STDOUT)
assert p.returncode==0,'Burst cache failed'
report=json.loads((R/'cache/combustion-burst/report.json').read_text(encoding='utf-8'))
assert report['frames']==120 and report['complete']
started=time.time()
with (R/'combustion-final-light.log').open('w',encoding='utf-8') as log:
    p=subprocess.run([sys.executable,str(R/'relight_combustion.py'),'--cache','combustion-burst','--output','combustion','--frames','all','--exposure','1.2'],stdout=log,stderr=subprocess.STDOUT)
assert p.returncode==0,'Relight failed'
files=[R/'frames/combustion'/f'{f:04}.jpg' for f in range(120)]
assert all(p.exists() and p.stat().st_mtime>=started for p in files),'Stale final frames'
source=hashlib.sha256(b''.join((R/k).read_bytes() for k in ['reactive.py','burst.py','relight_combustion.py'])).hexdigest()
receipt={'id':'combustion','frames':120,'fresh':True,'sourceHash':source,'started':started,'seconds':round(time.time()-started,2),'solver':'3D low-Mach reactive flow; not a compressible shock solve'}
(R/'receipts/combustion.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
subprocess.run([sys.executable,str(R/'encode.py'),'combustion'],check=True)
print('Combustion complete and verified',flush=True)
