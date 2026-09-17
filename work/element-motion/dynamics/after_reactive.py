"""Finish the next review pass after the owned reactive GPU bake exits."""
import sys,time,json,subprocess
from pathlib import Path
import psutil
R=Path(__file__).resolve().parent
pid=int(sys.argv[1])
try:
    proc=psutil.Process(pid)
    assert any(a.replace('\\','/').endswith('/dynamics/reactive.py') for a in proc.cmdline()),'Wrong process'
    proc.wait()
except psutil.NoSuchProcess:pass
assert (R/'combustion-report.json').exists(),'Reactive bake did not finish'
for kind,n in [('snow',42000),('sand',70000)]:
    with (R/f'mpm-{kind}.log').open('w',encoding='utf-8') as log:
        p=subprocess.run([sys.executable,str(R/'mpm.py'),kind,'--particles',str(n),'--frames','120'],stdout=log,stderr=subprocess.STDOUT)
    assert p.returncode==0,kind
    with (R/f'secondary-{kind}.log').open('w',encoding='utf-8') as log:
        p=subprocess.run([sys.executable,str(R/'granular_secondary.py'),kind],stdout=log,stderr=subprocess.STDOUT)
    assert p.returncode==0,kind
    print('SIMULATED',kind,flush=True)
jobs=['render_mpm.py:snow:30,45,65,90','render_mpm.py:sand:30,45,65,90','render_mpm.py:metal:30,45,65',
      'render_foam.py:foam:30,45,65','render_phase.py:ice:30,45,65','render_phase.py:glass:30,45,65','render_phase.py:lava:30,45,65',
      'render_liquid.py:mud:30,45,65','render_liquid.py:blood:30,45,65','render_crystal.py:crystal:30,45,65','render_botanical.py:healing:30,45,65',
      'render_fields.py:energy:32,45,65','render_fields.py:spirit:32,45,65','render_fields.py:sound:32,45,65','render_fields.py:seismic:32,45,65',
      'discharge.py:lightning-redirection:10,33,52']
result=subprocess.run([sys.executable,str(R/'pilot.py'),*jobs]);print('REVIEW PASS FINISHED',result.returncode,flush=True)
