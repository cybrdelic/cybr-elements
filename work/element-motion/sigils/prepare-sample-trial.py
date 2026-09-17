from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'render.py').read_text()
s=s.replace('s.cycles.samples=96 if K not in','s.cycles.samples=32 if K not in')
s=s.replace("progressdir=R/'progress'","progressdir=R/'progress-s32'")
s=s.replace("out=R/'frames'/f'{K}-{V}'","out=R/'frames'/f'{K}-{V}-s32'")
s=s.replace("R/f'render-{K}-{V}.json'","R/f'render-s32-{K}-{V}.json'")
(R/'render-s32.py').write_text(s,encoding='utf-8')
