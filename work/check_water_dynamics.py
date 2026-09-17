from pathlib import Path
import numpy as np,math,json
import sans_motion as font
p=Path(__file__).with_name('render_water_sans.py').read_text()
exec(p[p.index('groups=[];now='):p.index('angles=np.arange')])
exec(p[p.index('def simulate('):p.index('def surface(')])
rows=[]
for frame in range(450):
    for sub in range(4):simulate((frame+sub/4)/30,1/120)
    if frame in [239,329,345,375,449]:
        pos=np.concatenate([g['p'] for g in groups]);v=np.concatenate([g['v'] for g in groups])
        assert np.isfinite(pos).all() and np.isfinite(v).all()
        rows.append({'frame':frame,'maxSpeed':float(np.linalg.norm(v,axis=1).max()),'meanHeight':float(pos[:,2].mean()),'brokenLinks':sum(int(g['broken'].sum()) for g in groups)})
assert rows[-1]['meanHeight']<0,rows
Path(__file__).with_name('water-dynamics-check.json').write_text(json.dumps(rows,indent=2))
print(rows)
