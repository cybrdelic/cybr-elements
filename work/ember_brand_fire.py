"""Tracked contour pass on the existing native fire renders."""
from pathlib import Path
import json,subprocess,sys
import cv2,numpy as np
from scipy.ndimage import distance_transform_edt
from PIL import Image
cv2.setNumThreads(0)
ROOT=Path(__file__).parent;OUT=ROOT.parent/'outputs'
art=np.array(Image.open(OUT/'cybrdelic-type/exploration-v6/cybrdelic-brandmark-refined.png').convert('L'))
W,H,FPS=1920,1080,30
CW,CH=960,540
PREVIEW='--preview' in sys.argv
for variant in [v for v in sys.argv[1:] if v!='--preview'] or ['01','02']:
    data=np.load(ROOT/f'brand-fire-{variant}.npz');times=data['times'];points=data['points']
    top,bottom=(95,535) if variant=='01' else (585,1005)
    m=(art[top:bottom,20:1005]<100).astype('uint8')
    n,labs,stats,centers=cv2.connectedComponentsWithStats(m)
    for j in range(1,n):
        if stats[j,4]<35 or (centers[j,0]<85 and centers[j,1]<130):m[labs==j]=0
    yy,xx=np.where(m);m=m[yy.min():yy.max()+1,xx.min():xx.max()+1]
    scale=8.05/m.shape[1]
    distance=(distance_transform_edt(m)-distance_transform_edt(1-m)).astype('float32')
    distance=cv2.GaussianBlur(distance,(0,0),1.0)
    arrival=data['arrival'];nearest=distance_transform_edt(1-data['supply'],return_distances=False,return_indices=True)
    arrival=arrival[tuple(nearest)].astype('float32')
    diag=json.loads((OUT/f'cybrdelic-brand-{variant}-verification.json').read_text())['simulationDiagnostics']
    dtimes=[d['time'] for d in diag];reaction=[d['reaction'] for d in diag];reference=np.interp(10.5,dtimes,reaction)
    cap=cv2.VideoCapture(str(OUT/f'cybrdelic-brand-{variant}-fire.mp4'),cv2.CAP_FFMPEG,[cv2.CAP_PROP_N_THREADS,1])
    dest=OUT/f'cybrdelic-brand-{variant}-fire-ember.mp4'
    enc=None if PREVIEW else subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{W}x{H}','-r','30','-i','-','-an','-c:v','libx264','-threads','4','-preset','fast','-crf','15','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],stdin=subprocess.PIPE)
    cached=None
    for frame in ([90,225,315,360,449] if PREVIEW else range(450)):
        if PREVIEW:cap.set(cv2.CAP_PROP_POS_FRAMES,frame)
        ok,pixels=cap.read();assert ok,frame
        physical=frame/16;screen=frame/30
        combustion=1 if screen<11 else np.clip(np.interp(screen,dtimes,reaction)/reference,0,1)**.5
        if combustion<1e-7:
            if enc:enc.stdin.write(pixels.tobytes())
            if frame==449:cv2.imwrite(str(ROOT/f'ember-{variant}-{frame}.jpg'),cv2.resize(pixels,(1280,720)))
            continue
        follows=np.mean(np.interp(np.clip(physical+np.linspace(-1.2,.35,18)-.08,0,times[-1]),times,points[:,0]))
        zoom=np.clip((screen-5.55)/1.9,0,1);zoom=zoom*zoom*(3-2*zoom)
        camera=follows*(1-zoom);width=6.4+5*zoom;height=width*9/16
        x=np.linspace(camera-width/2,camera+width/2,CW,dtype='float32');z=np.linspace(2.35+height/2,2.35-height/2,CH,dtype='float32')
        vx,vz=np.meshgrid(x,z)
        sx=(vx/scale+m.shape[1]/2).astype('float32');sy=(m.shape[0]-(vz-.43)/scale).astype('float32')
        if cached is None:
            d=cv2.remap(distance,sx,sy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=-1000)*scale*(CW-1)/width
            at=cv2.remap(arrival,((vx+5.25)/10.5*511).astype('float32'),(vz/5.8*319).astype('float32'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=1e5)
            active=np.clip((physical-at-.20)/1.40,0,1)
            active=active*active*(3-2*active)
            contour=(np.exp(-(d/.75)**2)*.52+np.exp(-(d/2.0)**2)*.14)*active
            if frame>=245:cached=contour
        else:contour=cached
        small=cv2.resize(pixels,(CW,CH),interpolation=cv2.INTER_AREA)
        heat=np.clip(cv2.GaussianBlur(small[:,:,2].astype('float32'),(0,0),3)/170,0,1)
        strength=contour*(.18+.82*heat)*combustion
        glow=(strength[:,:,None]*np.array([18,78,175],dtype='float32')).astype('uint8')
        # Add soft, locally fire-modulated emission; no opaque line or black border.
        result=cv2.add(pixels,cv2.resize(glow,(W,H),interpolation=cv2.INTER_LINEAR))
        if enc:enc.stdin.write(result.tobytes())
        if frame in [90,225,315,360,449]:cv2.imwrite(str(ROOT/f'ember-{variant}-{frame}.jpg'),cv2.resize(result,(1280,720)))
        if frame%90==0:print(f'{variant}: {frame}/450',flush=True)
    cap.release()
    if PREVIEW:continue
    enc.stdin.close();assert enc.wait()==0
    meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames,duration','-of','json',str(dest)]))
    assert meta['streams'][0]['nb_read_frames']=='450'
    (OUT/f'cybrdelic-brand-{variant}-ember-verification.json').write_text(json.dumps({'video':str(dest),'metadata':meta,'contourSource':'study 06 silhouette','tracking':'same camera; smooth 0.75s emergence after ignition','treatment':'soft additive ember edge modulated by nearby flame, no dark border','burnout':'measured native reaction rate'},indent=2))
    print(str(dest),flush=True)
