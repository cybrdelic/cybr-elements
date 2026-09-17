from pathlib import Path
import sys
sys.path.insert(0,'work')
from gesture_motion import WRITE
s=Path('work/render_fire_hq.py').read_text()
s=s.replace('from intro_hq_motion import','from gesture_motion import')
s=s.replace("ROOT/'fire-hq-frames'","ROOT/'gesture-preview-frames'").replace("'cybrdelic-fire-hq.mp4'","'cybrdelic-fire-gesture.mp4'").replace("'fire-hq-report.json'","'gesture-report.json'")
s=s.replace("'9.5'",repr(str(round(WRITE+1.5,2))))
s=s.replace('across/.085','across/.115').replace('along/.060','along/.065')
s=s.replace('    pixels=(np.clip(rgb*falloff[:,None,None],0,1)*255).astype(np.uint8)', '''    horizontal=np.clip(np.minimum(np.arange(W)-55,W-56-np.arange(W))/145,0,1)
    horizontal=horizontal*horizontal*(3-2*horizontal)
    closing=min(1,max(0,(TOTAL-1-frame)/(FPS*.6)))
    pixels=(np.clip(rgb*falloff[:,None,None]*horizontal[None,:,None]*closing,0,1)*255).astype(np.uint8)''')
Path('work/render_gesture.py').write_text(s)
print(f'Continuous gesture: {WRITE:.2f} seconds plus decay; one always-moving source.')
