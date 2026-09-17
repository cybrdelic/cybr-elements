"""Read actual render, review and publication receipts; keep progress factual."""
from pathlib import Path
import json
from datetime import datetime, timezone

root = Path(__file__).resolve().parent / 'sigil-02-active-elements'
def read(name):
    path = root / name
    return json.loads(path.read_text()) if path.exists() else {}

published = read('publication.json').get('artifacts', {})
browser = read('browser-verification.json').get('verified', {})
elements = {}
for kind in ['water', 'lightning', 'lava', 'ice']:
    audit = read(f'{kind}-audit.json')
    folder = root / ('water-full' if kind == 'water' else kind) / 'frames'
    count = len(list(folder.glob('[0-9][0-9][0-9][0-9].jpg')))
    phase = 'published' if kind in published else 'awaiting visual review' if audit else 'rendering'
    elements[kind] = dict(phase=phase, framesOnDisk=count,
        decodedFrames=audit.get('decodedFrames'),
        visuallyReviewed=audit.get('visualStatus') == 'agent-reviewed',
        browserVerified=kind in browser, movie=published.get(kind))

complete = all(e['phase'] == 'published' and e['visuallyReviewed'] and e['browserVerified'] for e in elements.values())
state = dict(status='complete' if complete else 'in progress',
    checkedAt=datetime.now(timezone.utc).isoformat(), elements=elements,
    userAccepted=False, protected=['fire', 'air', 'earth'])
temporary = root / 'STATUS.tmp.json'
temporary.write_text(json.dumps(state, indent=2))
temporary.replace(root / 'STATUS.json')
for kind, entry in elements.items():
    if entry['phase'] != 'published':
        print(f"{kind}: {entry['phase']}; {entry['framesOnDisk']}/300 render frames on disk")
if complete:
    print('All four films published, visually reviewed and verified in the player.')
