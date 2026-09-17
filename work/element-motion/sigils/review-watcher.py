"""Prepare decoded evidence as encodes finish. Does not approve visual quality."""
from pathlib import Path
import json,subprocess,sys,time,hashlib
R=Path(__file__).resolve().parent;ROOT=R.parents[2]
kinds=[m['id'] for m in json.loads((ROOT/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/studies.json').read_text())]
done={};failures={}
while len(done)<len(kinds):
    for kind in kinds:
        keys=[kind+'-'+v for v in ['01','02']]
        if any(not (R/'media'/f'{key}.json').exists() for key in keys):continue
        hashes=[];valid=True
        for key in keys:
            meta=json.loads((R/'media'/f'{key}.json').read_text());digest=hashlib.sha256((R/'media'/f'{key}.mp4').read_bytes()).hexdigest()
            if meta['sha256']!=digest:valid=False;break
            hashes.append(digest)
        if not valid or done.get(kind)==hashes:continue
        try:
            with (R/f'evidence-{kind}.log').open('w') as log:
                missing=[]
                for key,digest in zip(keys,hashes):
                    proof=R/'sequence-check'/f'{key}.json'
                    if not proof.exists() or json.loads(proof.read_text())['sha256']!=digest:missing.append(key)
                if missing:subprocess.run([sys.executable,str(R/'sequence-check.py'),*missing],stdout=log,stderr=subprocess.STDOUT,check=True)
                subprocess.run([sys.executable,str(R/'review_pair.py'),kind],stdout=log,stderr=subprocess.STDOUT,check=True)
            done[kind]=hashes;print('READY FOR VISUAL REVIEW',kind,len(done),'/ 26',flush=True)
        except Exception as e:
            failures[kind]=failures.get(kind,0)+1;print('Evidence failed',kind,str(e),flush=True)
            if failures[kind]>=3:raise
    (R/'evidence-state.json').write_text(json.dumps({'ready':list(done),'pending':[k for k in kinds if k not in done],'failures':failures},indent=2))
    if len(done)<len(kinds):time.sleep(20)
print('All 52 films decoded; 26 paired review sheets prepared',flush=True)
