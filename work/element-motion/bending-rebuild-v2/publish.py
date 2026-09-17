from pathlib import Path
import cv2, hashlib, json, shutil, subprocess
import numpy as np
from PIL import Image

B=Path(__file__).resolve().parent
P=B.parents[2]/'outputs/cybrdelic-type/elements/motion/bending'
old=json.loads((B.parent/'bending-rebuild/validation.json').read_text())
checks={}
for name in ['earth','fire','air']:
    expected=next(v['sha256'] for v in old['videos'] if v['element']==name)
    actual=hashlib.sha256((P/f'{name}.mp4').read_bytes()).hexdigest()
    assert expected==actual, f'{name} changed'
    checks[name]=actual

results=[]
for name,poster in [('water',42),('lightning',39)]:
    path=B/f'{name}-v2.mp4'
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height,pix_fmt,r_frame_rate,duration,nb_frames','-of','json',str(path)]))['streams'][0]
    assert (probe['width'],probe['height'],probe['nb_frames'],probe['r_frame_rate'])==(1920,1080,'120','30/1')
    c=cv2.VideoCapture(str(path));frames=0;means=[];corners=[];crossings=[];maxima=[]
    while True:
        ok,a=c.read()
        if not ok:break
        if frames==poster:
            Image.fromarray(cv2.cvtColor(a,cv2.COLOR_BGR2RGB)).save(B/f'{name}-v2.jpg',quality=94)
        cornerValues=[float(np.quantile(p,.95)) for p in [a[:24,:24],a[:24,-24:],a[-24:,:24],a[-24:,-24:]]]
        if max(cornerValues)>3:crossings.append({'frame':frames,'corner95RGB':cornerValues})
        # A falling sheet enters the lower-right corner late in the shot.
        # Judge the remaining background, retaining crossings for visual review.
        means.append(round(float(a.mean()),5));corners.append(float(np.median(cornerValues)));maxima.append(int(a.max()));frames+=1
    c.release()
    assert frames==120
    assert max(corners)<=3, f'{name} raised black background'
    assert max(maxima)>=235
    results.append({'element':name,'file':path.name,'metadata':probe,'decodedFrames':frames,'medianCorner95MaximumRGB':max(corners),'foregroundCornerCrossings':crossings,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size,'frameMeanRGB':means})

m=json.loads((B/'water-particles/manifest.json').read_text());f=m['frames'][-1]
assert m['complete'] and len(m['frames'])==120 and f['pressureFailures']==0
assert all(x['finite'] and x['sourceVolumeBalance']==0 and x['capacityRejected']==0 for x in m['frames'])
meshes=[json.loads(p.read_text()) for p in sorted((B/'water-mesh-smooth').glob('[0-9][0-9][0-9][0-9].json'))]
assert len(meshes)==120
validation={'passed':True,'unchangedAcceptedClips':checks,'videos':results,'water':{'frames':120,'finite':True,'pressureFailures':0,'pressureSolves':f['pressureSolves'],'particles':f['particles'],'nominalSourceVolumeBalance':f['sourceVolumeBalance'],'maxReconstructionRelativeVolumeError':max(abs(x.get('totalRepresentedVolumeError',0)) for x in meshes)},'reviewImages':['water-comparison.jpg','water-late-review.jpg','lightning-comparison.jpg','lightning-timing.jpg']}
(B/'validation.json').write_text(json.dumps(validation,indent=2))

provenance=json.loads((P/'provenance.json').read_text())
provenance['revision']='water-lightning-rebuild-2'
provenance['elements']['water']={
 'file':'water-v2.mp4','previous':'water.mp4','dynamics':'Fresh quadratic APIC/FLIP simulation with pressure projection and capillary surface tension; art-directed nozzle turning and gravity ramp',
 'grid':[234,156,40],'h':.018,'particles':f['particles'],'pressureFailures':0,
 'render':'Cycles OptiX, 2560 x 1440, 64 samples; downsampled to 1920 x 1080',
 'changes':['Rotating elliptical nozzle produces a broader rolling sheet','Anisotropic surface reconstruction, separate volume-carrying droplets','Black environment for camera and transmission; area-light reflections','Collision floor placed below camera framing'],
 'optics':{'ior':1.333,'roughness':.006,'volumeAbsorption':True},
 'limitations':['Grid and particle resolution limit the smallest sheet and droplet scales','Global reconstruction volume matching is not a local conservation proof']}
provenance['elements']['lightning']={
 'file':'lightning-v2.mp4','previous':'lightning.mp4','dynamics':'Stochastic dielectric-breakdown growth in a 2D Laplace potential field, mapped into the shared authored motion corridor',
 'render':'CPU 2x supersampling, hierarchical channel radiance, linear-light corona',
 'changes':['Connected field-grown fork topology','Separate faint leaders, strong strokes, and repeated return strokes','Primary channel brighter than secondary and tertiary forks','Brief frame-integrated discharge exposure'],
 'limitations':['Guided 2D graphics model, not full 3D plasma electrodynamics','Laplace relaxation is approximate during growth'],
 'reference':'https://gamma-web.iacs.umd.edu/LIGHTNING/lightning.pdf'}
provenance['limitations']=['Bending paths and forces are authored for the shared motion.','Water uses resolved FLIP/APIC dynamics; unresolved microscale detail is limited by discretization.','Lightning uses guided 2D dielectric-breakdown growth rather than a full plasma solver.']
provenance['rebuildValidation']={'videos':[{k:v for k,v in r.items() if k!='frameMeanRGB'} for r in results],'water':validation['water'],'unchangedAcceptedClips':checks}
for name in ['water','lightning']:
    for ext in ['mp4','jpg']:shutil.copy2(B/f'{name}-v2.{ext}',P/f'{name}-v2.{ext}')
(P/'provenance.json').write_text(json.dumps(provenance,indent=2))
shutil.copy2(B/'index.html',P/'index.html')
print(json.dumps({'published':True,'videos':[{k:v for k,v in r.items() if k not in ('frameMeanRGB','sha256','foregroundCornerCrossings')} for r in results],'water':validation['water'],'unchanged':list(checks)},indent=2))
