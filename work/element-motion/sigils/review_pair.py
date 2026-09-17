"""Decode bounded contact sheets of the actual final video files."""
from pathlib import Path
import subprocess, sys, json, hashlib
from PIL import Image
R=Path(__file__).resolve().parent
for kind in sys.argv[1:]:
    keys=[kind+'-'+v for v in ['01','02']]
    stale=[]
    for key in keys:
        proof=R/'review'/f'{key}.json'
        digest=hashlib.sha256((R/'media'/f'{key}.mp4').read_bytes()).hexdigest()
        if not proof.exists() or json.loads(proof.read_text())['videoSha256']!=digest:stale.append(key)
    if stale:subprocess.run([sys.executable,str(R/'review.py'),*stale],check=True,stdout=subprocess.DEVNULL)
    sheet=Image.new('RGB',(1280,800))
    for i,key in enumerate(keys):sheet.paste(Image.open(R/'review'/f'{key}.jpg'),(0,i*400))
    path=R/'review'/f'{kind}-pair.jpg';sheet.save(path,quality=93)
    print(path,flush=True)
