"""Record a human/model visual inspection, bound to the reviewed video hashes."""
from pathlib import Path
import sys,json,hashlib
R=Path(__file__).resolve().parent
kind,note=sys.argv[1:3]
record={};samples=[]
for variant in ['01','02']:
    key=kind+'-'+variant
    proof=json.loads((R/'review'/f'{key}.json').read_text())
    digest=hashlib.sha256((R/'media'/f'{key}.mp4').read_bytes()).hexdigest()
    assert proof['videoSha256']==digest,'Review is stale'
    record[variant]=digest;samples=proof['frames']
file=R/'reviews.json'
data=json.loads(file.read_text()) if file.exists() else {}
data[kind]={'videoHashes':record,'sampledFrames':samples,'observation':note,'scope':'Original sigil, sequence, black framing and encode review; not certification of physical realism.'}
file.write_text(json.dumps(data,indent=2),encoding='utf-8')
print('Recorded visual review:',kind)
