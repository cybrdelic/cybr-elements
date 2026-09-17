"""Build the version selector only after every referenced clip is validated."""
from pathlib import Path
import json
B=Path(__file__).resolve().parent;P=B.parents[2]/'outputs/cybrdelic-type/elements/motion/bending'
config=json.loads((B/'selection.json').read_text())
for name,entry in config.items():
    for kind in ['previous','rebuilt']:
        for ext in ['mp4','jpg']:assert (P/(entry[kind]+'.'+ext)).exists()
s=(B/'baseline/index.html').read_text(encoding='utf-8')
s=s.replace("const revised=new Set(['water','lightning']);","const variants="+json.dumps(config)+";\nconst revised=new Set(elements.map(e=>e[0]));")
s=s.replace("const stem=revised.has(id)?`${id}-v4`:id;", "const initial=variants[id].selected,stem=variants[id][initial];")
s=s.replace('data-version="rebuilt" style=', 'data-version="${initial}" style=')
s=s.replace('data-version="previous" aria-pressed="false">Previous', 'data-version="previous" aria-pressed="${initial===\'previous\'}">Previous')
s=s.replace('data-version="rebuilt" aria-pressed="true">Rebuilt', 'data-version="rebuilt" aria-pressed="${initial===\'rebuilt\'}">Trial')
s=s.replace("const stem=card.id+(kind==='rebuilt'?'-v4':'-v3');", "const stem=variants[card.id][kind];")
s=s.replace("wasTogether=together,wasPlaying", "wasTogether=together&&!selected.paused,wasPlaying")
# Both sets are retained. The user can compare any element without changing others.
(P/'index.html').write_text(s,encoding='utf-8')
print('Player updated with independent Previous / Trial controls for all five elements.')
