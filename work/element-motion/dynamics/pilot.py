from pathlib import Path
import subprocess,sys,json,time
R=Path(__file__).resolve().parent
blender='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
report=[]
for spec in sys.argv[1:]:
    script,kind,frames=spec.split(':')
    started=time.time()
    with (R/f'pilot-{kind}.log').open('w',encoding='utf-8') as log:
        p=subprocess.run([blender,'--factory-startup','-b','-t','3','--python-exit-code','1','--python',str(R/script),'--','--kind',kind,'--frames',frames],stdout=log,stderr=subprocess.STDOUT)
    tail=(R/f'pilot-{kind}.log').read_bytes()[-3000:].decode('utf-8',errors='replace')
    files=[R/'frames'/kind/f'{int(f):04}.jpg' for f in frames.split(',')]
    ok=p.returncode==0 and all(p.exists() and p.stat().st_mtime>=started for p in files)
    report.append({'id':kind,'ok':ok,'frames':frames});print(kind,'OK' if ok else tail[-1200:].encode('ascii','replace').decode(),flush=True)
(R/'pilot-status.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(0 if all(row['ok'] for row in report) else 1)
