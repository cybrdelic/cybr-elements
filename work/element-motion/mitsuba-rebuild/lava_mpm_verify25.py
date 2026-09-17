"""Serial CPU validation; do not overlap these jobs with simulation/rendering."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
from pathlib import Path
import subprocess,sys,time,json
here=Path(__file__).parent;folder=here/'lava-focus/mpm/rebuild-25';results={}
scripts=['lava_mpm_rebuild25_check.py','lava_mpm_rebuild_suite.py','lava_mpm_rebuild_smoke.py','lava_mpm_surface25_check.py','lava_mpm_gap25_check.py','lava_material_texture_check.py','lava_mpm_rebuild_comparison.py']
for script in scripts:
    start=time.monotonic();log=folder/(script.removesuffix('.py')+'-verified.log')
    with log.open('w') as output:process=subprocess.run([sys.executable,str(here/script)],stdout=output,stderr=subprocess.STDOUT)
    result=dict(exitCode=process.returncode,seconds=time.monotonic()-start,log=str(log));results[script]=result;print(json.dumps(dict(script=script,**result)),flush=True)
    if process.returncode:
        print('\n'.join(log.read_text(errors='replace').splitlines()[-18:]));break
status='pass' if len(results)==len(scripts) and all(q['exitCode']==0 for q in results.values()) else 'fail'
(folder/'serial-validation.json').write_text(json.dumps(dict(status=status,runs=results),indent=2));raise SystemExit(status!='pass')
