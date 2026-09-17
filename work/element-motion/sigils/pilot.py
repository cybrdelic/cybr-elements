from pathlib import Path
import sys,subprocess,time,json
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;B='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
results=[];cpu='--cpu' in sys.argv
for item in [x for x in sys.argv[1:] if x!='--cpu']:
    kind,variant,frames=item.split(':');start=time.time();log=R/f'pilot-{kind}-{variant}.log'
    with log.open('w',encoding='utf-8') as out:
        command=[B,'--factory-startup','-b','-t','3','--python-exit-code','1','--python',str(R/'render.py'),'--','--kind',kind,'--variant',variant,'--frames',frames]
        if cpu:command.append('--cpu')
        p=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT)
    paths=[R/'frames'/f'{kind}-{variant}'/f'{int(f):04}.jpg' for f in frames.split(',')]
    fresh=p.returncode==0 and all(p.exists() and p.stat().st_mtime>=start-1 for p in paths)
    results.append({'kind':kind,'variant':variant,'fresh':fresh,'seconds':time.time()-start})
    print('PILOT',kind,variant,fresh,round(time.time()-start,1),flush=True)
    if not fresh:raise RuntimeError('Inspect '+str(log))
    for path in paths:
        im=Image.open(path);im.thumbnail((1280,720));im.save(R/f'pilot-{kind}-{variant}-{path.stem}.jpg',quality=94)
(R/'pilot-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
