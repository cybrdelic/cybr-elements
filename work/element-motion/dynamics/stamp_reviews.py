"""Bind manual review notes to the actual decoded candidate video."""
from pathlib import Path
import json
R=Path(__file__).resolve().parent;path=R/'visual-review.json';reviews=json.loads(path.read_text(encoding='utf-8'))
for k,note in reviews.items():
    if not note.get('sampledSequenceReviewed'):continue
    media=json.loads((R/'media'/f'{k}.json').read_text(encoding='utf-8'));sheet=json.loads((R/'sequence-review'/f'{k}.json').read_text(encoding='utf-8'))
    assert sheet['videoSha256']==media['sha256'],(k,'Review contact sheet is stale')
    assert note.get('videoSha256',media['sha256'])==media['sha256'],(k,'Previously reviewed video was replaced; review again')
    note['videoSha256']=media['sha256']
path.write_text(json.dumps(reviews,indent=2),encoding='utf-8');print('Bound',len(reviews),'manual reviews to decoded video hashes')
