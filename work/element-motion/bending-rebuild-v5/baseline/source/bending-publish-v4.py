"""Validate complete delivery before updating the existing player."""
from pathlib import Path
import json,subprocess,shutil,hashlib
from PIL import Image
import cv2,numpy as np
R=Path(__file__).resolve().parent;B=R/'bending-rebuild-v4';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending'
checks={}
for name in ['water','lightning']:
    clip=B/f'{name}-v4.mp4'
    data=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=width,height,avg_frame_rate,nb_frames,color_range,color_space:format=duration','-of','json',str(clip)],text=True))
    s=data['streams'][0];assert (s['width'],s['height'],s['nb_frames'],s['avg_frame_rate'])==(1920,1080,'120','30/1');assert float(data['format']['duration'])==4
    cap=cv2.VideoCapture(str(clip));count=0;corner=0
    while True:
        ok,frame=cap.read()
        if not ok:break
        assert np.isfinite(frame).all();corner=max(corner,float(frame[:25,:25].mean()),float(frame[:25,-25:].mean()));count+=1
    cap.release();assert count==120 and corner<.1
    checks[name]=dict(metadata=data,decodedFrames=count,maximumTopCornerLevel=corner,sha256=hashlib.sha256(clip.read_bytes()).hexdigest())
    shutil.copy2(clip,P/clip.name)
for name,f in [('water',58),('lightning',38)]:
    folder='water-final-frames' if name=='water' else 'lightning-frames'
    im=Image.open(B/folder/f'{f:04}.jpg');im.resize((1920,1080),Image.Resampling.LANCZOS).save(P/f'{name}-v4.jpg',quality=95)
for name,digest in json.loads((B/'unchanged-elements.json').read_text()).items():assert hashlib.sha256((P/f'{name}.mp4').read_bytes()).hexdigest()==digest
page=P/'index.html';s=page.read_text(encoding='utf-8');s=s.replace('`${id}-v3`','`${id}-v4`').replace("kind==='rebuilt'?'-v3':'-v2'","kind==='rebuilt'?'-v4':'-v3'");page.write_text(s,encoding='utf-8')
p=json.loads((P/'provenance.json').read_text());w=p['elements']['water'];w.update(file='water-v4.mp4',previous='water-v3.mp4',particles=65992,dynamics='234 x 157 x 84 APIC/FLIP, h 0.018; rounded source with 3D centre and tangent, pressure/capillary solve; authored lift and steering',camera='Perspective, 45mm, oblique view at [2.8,-13,3.3]',lighting='Camera-black world with studio reflection/refraction illumination and area lights',validation=json.loads((B/'water-report.json').read_text()))
l=p['elements']['lightning'];l.update(file='lightning-v4.mp4',previous='lightning-v3.mp4',dynamics='3D point-charge Laplacian growth with authored sequential electrodes and competing off-axis attraction',atmosphere='200 x 112 x 48 advected aerosol, buoyancy, FFT projection and approximate channel scattering through a perspective camera',render='Subpixel Gaussian channel profile, lattice-scale smoothing at nonbranching nodes, hierarchical exposure, irregular return-stroke events',limitations=['This is a point-charge graphics growth model, not a full plasma or shock solver.','The bending controls and aerosol source are authored.','Channel scattering uses a nearest-channel approximation.'],reference='https://faculty.cc.gatech.edu/~turk/bio_sim/articles/laplacian_growth.pdf',validation=json.loads((B/'lightning-report.json').read_text()))
p['delivery']['camera']={'earthFireAir':'Original camera preserved','water':'Oblique perspective','lightning':'Perspective; 3D growth and volume'}
p['limitations']=['Guided effects with authored bending forces and controlled release.','Water atomization is a volume-accounted subgrid parcel closure.','Lightning is 3D Laplacian growth with approximate exposure and aerosol transport; not full plasma electrodynamics.','Water is still quite uniform early in the shot; lightning remains a guided stylized discharge.']
(P/'provenance.json').write_text(json.dumps(p,indent=2),encoding='utf-8');(B/'delivery-validation.json').write_text(json.dumps(checks,indent=2))
print('Published both 1080p clips: 120 decoded frames each; top corners black; earth/fire/air checksums unchanged; Previous selects v3.')
