"""Reversibly repack derived PNG caches as verified lossless RGB video chunks."""
from pathlib import Path
import subprocess, hashlib, json, sys
import cv2
from PIL import Image
import numpy as np

B=Path(__file__).resolve().parent;W=B.parents[1];name=sys.argv[1]
assert name in ['water-brand-01-frames','water-brand-02-frames']
source=(W/name).resolve();assert source.parent==W.resolve()
archive=B/'lossless-frame-archives'/name;archive.mkdir(parents=True,exist_ok=True)
manifest=archive/'manifest.json';records=json.loads(manifest.read_text()) if manifest.exists() else []
for start in range(0,450,50):
    if any(r['start']==start for r in records):continue
    files=[source/f'{f:04}.png' for f in range(start,start+50)];assert all(p.exists() for p in files)
    clip=archive/f'{start:04}-{start+49:04}.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-threads','2','-framerate','30','-start_number',str(start),'-i',str(source/'%04d.png'),'-frames:v','50','-an','-c:v','libx264rgb','-threads','2','-preset','medium','-crf','0','-pix_fmt','rgb24',str(clip)],check=True)
    cap=cv2.VideoCapture(str(clip),cv2.CAP_FFMPEG,[cv2.CAP_PROP_N_THREADS,1]);hashes=[]
    for p in files:
        original=np.asarray(Image.open(p));assert original.shape==(2160,3840,3)
        ok,decoded=cap.read();assert ok
        decoded=cv2.cvtColor(decoded,cv2.COLOR_BGR2RGB);assert np.array_equal(original,decoded),p
        hashes.append(hashlib.sha256(original.tobytes()).hexdigest())
    assert not cap.read()[0];cap.release()
    record=dict(start=start,frames=50,archive=clip.name,pixelFormat='RGB24',size=[3840,2160],rgbSha256=hashes,sourceBytes=sum(p.stat().st_size for p in files),archiveBytes=clip.stat().st_size)
    records.append(record);manifest.write_text(json.dumps(records,indent=2),encoding='utf-8')
    for p in files:
        assert p.resolve().parent==source;p.unlink()
    print(name,start,'50 exact pixel matches; saved MiB',round((record['sourceBytes']-record['archiveBytes'])/1048576,1),flush=True)
print('COMPLETE',name,flush=True)
