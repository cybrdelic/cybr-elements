"""Decode every frame and report temporal integrity; visual review remains separate."""
from pathlib import Path
import sys,json,hashlib
import cv2,numpy as np
cv2.setNumThreads(1)
R=Path(__file__).resolve().parent;out=R/'sequence-check';out.mkdir(exist_ok=True)
for key in sys.argv[1:]:
    path=R/'media'/f'{key}.mp4';cap=cv2.VideoCapture(str(path));areas=[];changes=[];previous=None
    while True:
        ok,frame=cap.read()
        if not ok:break
        assert frame.shape[:2]==(1080,1920),(key,frame.shape)
        small=cv2.resize(frame,(320,180),interpolation=cv2.INTER_AREA)
        areas.append(int((small.max(2)>12).sum()))
        if previous is not None:changes.append(float(np.mean(np.abs(small.astype('f4')-previous))))
        previous=small.astype('f4')
    cap.release()
    assert len(areas)==450,(key,len(areas))
    assert max(areas)>60,('No visible content',key)
    active=np.flatnonzero(np.array(areas)>12)
    report={'id':key,'decodedFrames':len(areas),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'firstVisibleFrame':int(active[0]),'lastVisibleFrame':int(active[-1]),'lastFrameArea':areas[-1],'maximumFrameDifference':max(changes),'largestChanges':np.argsort(changes)[-5:].astype(int).tolist(),'visiblePixels':areas,'frameDifferences':changes}
    (out/f'{key}.json').write_text(json.dumps(report),encoding='utf-8')
    print(key,'450 decoded frames; last visible',active[-1],'; end pixels',areas[-1],flush=True)
