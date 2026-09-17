"""Bounded renderer queue; completed artifacts never imply an unreviewed pass."""
from pathlib import Path
import subprocess,json,time,sys,hashlib
R=Path(__file__).resolve().parent;B='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
if (R/'quality-hold.json').exists():raise SystemExit('Render stopped: material quality was rejected. Read quality-hold.json before starting new renders.')
fail=[]
for key in sys.argv[1:]:
    kind,variant=key.rsplit('-',1);log=R/f'full-{key}.log';start=time.time()
    renderer=R/('render-balanced.py' if kind in ['ice','foam','lava','mud','blood','crystal'] else 'render.py')
    deps=[renderer,*[R/n for n in ['materials.py','motion.py','botanical.py','channels.py']]];before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in deps}
    with log.open('w',encoding='utf-8') as out:
        p=subprocess.run([B,'--factory-startup','-b','-t','3','--python-exit-code','1','--python',str(renderer),'--','--kind',kind,'--variant',variant,'--resume'],stdout=out,stderr=subprocess.STDOUT)
    progress=R/'progress'/f'{key}.json';proof=json.loads(progress.read_text()) if progress.exists() else {}
    fresh=all((R/'frames'/key/f'{f:04}.jpg').exists() for f in range(450)) and set(proof.get('frames',[]))==set(range(450))
    changed=[name for name,h in before.items() if hashlib.sha256((R/name).read_bytes()).hexdigest()!=h]
    if p.returncode or not fresh or changed:
        print('FAILED',key,p.returncode,fresh,changed,flush=True);fail.append(key);continue
    proof={'id':key,'fresh':True,'sourceHashes':before,'seconds':time.time()-start};(R/f'receipt-{key}.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    p=subprocess.run([sys.executable,str(R/'encode.py'),key]);print('DONE',key,round(time.time()-start,1),p.returncode,flush=True)
    if p.returncode:fail.append(key)
if fail:raise SystemExit('Incomplete: '+', '.join(fail))
