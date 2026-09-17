"""Use the GPU for the burst pilot once our current render queues finish."""
import sys,subprocess,psutil
from pathlib import Path
R=Path(__file__).resolve().parent
for pid in map(int,sys.argv[1:]):
    try:
        p=psutil.Process(pid)
        assert any(x.replace('\\','/').endswith('/dynamics/render_all.py') for x in p.cmdline()),'Unowned queue'
        p.wait()
    except psutil.NoSuchProcess:pass
with (R/'repair-renders.log').open('w',encoding='utf-8') as log:
    result=subprocess.run([sys.executable,str(R/'render_all.py'),'metal','sand','snow','healing','glass','seismic'],stdout=log,stderr=subprocess.STDOUT)
print('Repair renders exit',result.returncode,flush=True)
with (R/'burst-pilot.log').open('w',encoding='utf-8') as log:
    result=subprocess.run([sys.executable,str(R/'burst.py')],stdout=log,stderr=subprocess.STDOUT)
print('Burst pilot exit',result.returncode,flush=True)
if result.returncode==0:
    with (R/'burst-relight.log').open('w',encoding='utf-8') as log:
        result=subprocess.run([sys.executable,str(R/'relight_combustion.py'),'--cache','combustion-burst','--output','combustion-burst-look','--frames','50,52,56,60,65','--exposure','1.2'],stdout=log,stderr=subprocess.STDOUT)
    print('Burst preview exit',result.returncode,flush=True)
