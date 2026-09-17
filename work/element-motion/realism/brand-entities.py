from pathlib import Path
R=Path(__file__).resolve().parent
for name in ['entities.py','spirit.py']:
 p=R/name;s=p.read_text(encoding='utf-8').replace('body,v=sculpture()','body,v=brandmark()')
 if name=='entities.py':
  s=s.replace("if K=='spirit-projection':\n  ghost=", "if K=='spirit-projection':\n  body.scale=(.35,.35,.35)\n  ghost=")
  s=s.replace("ghost.scale=(.93,.93,.93)","ghost.scale=(.35,.35,.35)")
 p.write_text(s,encoding='utf-8')
print('Abstract subjects now use the unchanged approved Cybrdelic Sigil SVG')
