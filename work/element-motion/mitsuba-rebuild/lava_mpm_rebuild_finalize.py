"""Sequential CPU checks, then publish only matching-source evidence."""
import subprocess,sys
from pathlib import Path


root=Path(__file__).resolve().parent
for script in ('lava_mpm_rebuild_suite.py','lava_mpm_rebuild_comparison.py','lava_mpm_rebuild_smoke.py','lava_mpm_rebuild_publish.py'):
    log=root/'lava-focus/mpm/rebuild-24'/f'{Path(script).stem}-final.log'
    with log.open('w',encoding='utf-8') as out:
        result=subprocess.run([sys.executable,str(root/script)],cwd=root,stdout=out,stderr=subprocess.STDOUT,timeout=180)
    print(script,'pass' if result.returncode==0 else 'fail',str(log),flush=True)
    if result.returncode:raise SystemExit(result.returncode)
