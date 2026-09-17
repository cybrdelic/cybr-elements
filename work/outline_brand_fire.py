"""Tracked contour pass on the existing native fire renders."""
from pathlib import Path
import json,subprocess,sys
import cv2,numpy as np
from scipy.ndimage import distance_transform_edt
from PIL import Image
cv2.setNumThreads(2)
ROOT=Path(__file__).parent;OUT=ROOT.parent/'outputs'
art=np.array(Image.open(OUT/'cybrdelic-type/exploration-v6/cybrdelic-brandmark-refined.png').convert('L'))
W,H,FPS=1920,1080,30
for variant in (sys.argv[1:] or ['01','02']):
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
    cap=cv2.VideoCapture(str(OUT/f'cybrdelic-brand-{variant}-fire.mp4'))
    dest=OUT/f'cybrdelic-brand-{variant}-fire-outlined.mp4'
    enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{W}x{H}','-r','30','-i','-','-an','-c:v','libx264','-threads','4','-preset','fast','-crf','15','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],stdin=subprocess.PIPE)
    cached=None
    for frame in range(450):
        ok,pixels=cap.read();assert ok,frame
        physical=frame/16;screen=frame/30
        combustion=1 if screen<11 else np.clip(np.interp(screen,dtimes,reaction)/reference,0,1)**.5
        if combustion<1e-7:
            enc.stdin.write(pixels.tobytes())
            if frame==449:cv2.imwrite(str(ROOT/f'outline-{variant}-{frame}.jpg'),cv2.resize(pixels,(1280,720)))
            continue
        follows=np.mean(np.interp(np.clip(physical+np.linspace(-1.2,.35,18)-.08,0,times[-1]),times,points[:,0]))
        zoom=np.clip((screen-5.55)/1.9,0,1);zoom=zoom*zoom*(3-2*zoom)
        camera=follows*(1-zoom);width=6.4+5*zoom;height=width*9/16
        x=np.linspace(camera-width/2,camera+width/2,W,dtype='float32');z=np.linspace(2.35+height/2,2.35-height/2,H,dtype='float32')
        vx,vz=np.meshgrid(x,z)
        sx=(vx/scale+m.shape[1]/2).astype('float32');sy=(m.shape[0]-(vz-.43)/scale).astype('float32')
        if cached is None:
            d=cv2.remap(distance,sx,sy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=-1000)*scale*(W-1)/width
            at=cv2.remap(arrival,((vx+5.25)/10.5*511).astype('float32'),(vz/5.8*319).astype('float32'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=1e5)
            active=np.clip((physical-at)/.08,0,1)
            darkbase=np.clip(4-np.abs(d),0,1)*active*.80
            corebase=np.clip(2.5-np.abs(d),0,1)*active*.95
            if frame>=225:cached=(darkbase,corebase)
        else:darkbase,corebase=cached
        dark=darkbase*combustion;core=corebase*combustion
        rgb=pixels.astype('float32')*(1-dark[...,None])
        # A thin amber keyline; the fluid frames are not altered or re-simulated.
        rgb=rgb*(1-core[...,None])+np.array([54,161,255],dtype='float32')*core[...,None]
        result=np.clip(rgb,0,255).astype('uint8');enc.stdin.write(result.tobytes())
        if frame in [90,225,315,360,449]:cv2.imwrite(str(ROOT/f'outline-{variant}-{frame}.jpg'),cv2.resize(result,(1280,720)))
        if frame%90==0:print(f'{variant}: {frame}/450',flush=True)
    cap.release();enc.stdin.close();assert enc.wait()==0
    meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames,duration','-of','json',str(dest)]))
    assert meta['streams'][0]['nb_read_frames']=='450'
    (OUT/f'cybrdelic-brand-{variant}-outline-verification.json').write_text(json.dumps({'video':str(dest),'metadata':meta,'contourSource':'study 06 original silhouette','tracking':'same camera and ignition arrival as solver','burnout':'outline intensity follows measured native reaction rate'},indent=2))
    print(str(dest),flush=True)
