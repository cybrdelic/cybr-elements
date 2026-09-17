from pathlib import Path
import subprocess,sys,json,hashlib
from PIL import Image
import numpy as np
R=Path(__file__).resolve().parent;O=R/'media';O.mkdir(exist_ok=True)
for kind in sys.argv[1:]:
    folder=R/'frames'/kind;files=[folder/f'{f:04}.jpg' for f in range(120)];corners=[];clearcorners=[];blackfractions=[];counts=[];digest=hashlib.sha256()
    for p in files:
        assert p.exists() and p.stat().st_size>400,(kind,p,'incomplete')
        with Image.open(p) as im:
            assert im.size==(1920,1080);a=np.array(im);tiles=[a[:12,:12],a[:12,-12:],a[-12:,:12],a[-12:,-12:]];corners.append(max(int(t.max()) for t in tiles));clearcorners.append(min(int(t.max()) for t in tiles));blackfractions.append(float(np.all(a<=3,axis=2).mean()));counts.append(int(np.any(a>10,axis=2).sum()))
        digest.update(p.read_bytes())
    # Moving foreground particles may cross a corner. Require a clear black
    # corner and predominantly black empty pixels, without deleting that motion.
    assert max(clearcorners)<=3 and min(blackfractions)>.50,(kind,'background check',max(clearcorners),min(blackfractions))
    assert max(counts)>500 and sum(n>100 for n in counts)>=6,(kind,'missing visible content')
    output=O/f'{kind}.mp4';subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-framerate','30','-i',str(folder/'%04d.jpg'),'-frames:v','120','-c:v','libx264','-threads','2','-preset','slow','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],check=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,nb_frames,duration','-of','json',str(output)],text=True))['streams'][0]
    assert (probe['width'],probe['height'],probe['avg_frame_rate'],probe['nb_frames'])==(1920,1080,'30/1','120')
    best=next((f for f in [45,50,39,33,65] if counts[f]>max(counts)*.3),int(np.argmax(counts)));Image.open(files[best]).save(O/f'{kind}.jpg',quality=95)
    receipt=R/'receipts'/f'{kind}.json';r=json.loads(receipt.read_text(encoding='utf-8')) if receipt.exists() else {'id':kind}
    r.update({'video':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'frameDigest':digest.hexdigest(),'blackCornerMax':max(corners),'clearCornerMax':max(clearcorners),'minimumBlackFraction':min(blackfractions),'nonblackPixelCounts':counts,**probe});(O/f'{kind}.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print('VERIFIED',kind,'120 HD frames, clear black corner',max(clearcorners),flush=True)
