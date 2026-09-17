from pathlib import Path
import sys,subprocess
R=Path(__file__).resolve().parent
for kind,n in [('sand',70000),('snow',42000)]:
    for script,args in [('mpm.py',[kind,'--particles',str(n),'--frames','120']),('granular_secondary.py',[kind])]:
        with (R/f'repair-{kind}-{script}.log').open('w',encoding='utf-8') as log:
            p=subprocess.run([sys.executable,str(R/script),*args],stdout=log,stderr=subprocess.STDOUT)
        assert p.returncode==0,(kind,script)
    print('Rebaked',kind,flush=True)
