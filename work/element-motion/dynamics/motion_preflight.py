"""Check particle framing before spending time on final-lighting renders."""
from pathlib import Path
import sys,json
import numpy as np
R=Path(__file__).resolve().parent
def check(kind):
    folder=R/'cache'/kind;birth=np.load(folder/'static.npz')['birth'];rows=[]
    for f in range(3,67,3):
        a=np.load(folder/f'{f:04}.npz');p=a['p'][birth<=float(a['t'])]
        if not len(p):continue
        assert np.isfinite(p).all(),(kind,f,'nonfinite positions')
        inside=(np.abs(p[:,0])<=5.25)&(p[:,2]>=-1.05)&(p[:,2]<=4.85625)
        rows.append({'frame':f,'outsideFraction':float(1-inside.mean()),'p01':np.quantile(p,[.01],axis=0)[0].tolist(),'p99':np.quantile(p,[.99],axis=0)[0].tolist()})
    worst=max(r['outsideFraction'] for r in rows);result={'id':kind,'checkedThroughSeconds':2.2,'maximumOutsideFraction':worst,'pass':worst<.15,'frames':rows,'limits':'A framing check only; it cannot establish material realism or validate a constitutive model.'}
    out=R/'preflight';out.mkdir(exist_ok=True);(out/f'{kind}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(kind,'preflight', 'PASS' if result['pass'] else 'FAIL',f'{worst:.1%} maximum outside the camera',flush=True)
    assert result['pass'],(kind,'Too much material leaves the camera during formation/hold; review forces before rendering')
if __name__=='__main__':
    for kind in sys.argv[1:]:check(kind)
