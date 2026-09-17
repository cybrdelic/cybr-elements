"""Resumable native-1080p capture of real, newly simulated Three.js frames.

A single browser is restarted every 16 simulation frames to bound software-GL
memory. Each camera image and its hashes are committed before moving forward.
A killed browser can never turn an incomplete recording into a completed film.
"""
from __future__ import annotations
from pathlib import Path
import argparse,base64,hashlib,json,re,time
from playwright.sync_api import sync_playwright
from browser_common import ROOT,launch
from record import Encoder
W,H,FPS=1920,1080,24
REPORT=ROOT/'tests/repair/captures';REPORT.mkdir(parents=True,exist_ok=True)
IMAGES=ROOT/'media/capture_frames';IMAGES.mkdir(parents=True,exist_ok=True)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def atomic_json(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2));tmp.replace(path)
def wait_frame(folder,frame,timeout=2400):
    start=time.time()
    while time.time()-start<timeout:
        try:
            manifest=json.loads((folder/'manifest.json').read_text())
            progress=json.loads((folder/'mesh-repair-progress.json').read_text())
            if len(manifest['frames'])>frame and progress['lastFrame']>=frame:
                info=manifest['frames'][frame];mesh=next(x for x in progress['meshes'] if x['frame']==frame)
                if (folder/f'{frame:04d}.mesh.gz').exists():return manifest,info,mesh
        except (OSError,ValueError,StopIteration):pass
        time.sleep(.5)
    raise TimeoutError(f'{folder.name}: frame {frame} not committed')
def open_scene(browser,scene,frames,errors):
    folder=ROOT/'cache'/scene;manifest,first,_=wait_frame(folder,0)
    fixed=dict(manifest);fixed.pop('meshes',None)
    fixed['frames']=[dict(first,frame=f,time=(f+1)/48) for f in range(frames)]
    fixed['frames'][0]=first
    page=browser.new_page(viewport={'width':W,'height':H},device_scale_factor=1)
    page.set_default_timeout(90000)
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    def read_cache(name,f):
        if name!=scene or not isinstance(f,int) or not 0<=f<frames:raise ValueError('Invalid cache request')
        return base64.b64encode((folder/f'{f:04d}.mesh.gz').read_bytes()).decode()
    page.expose_function('__readCache',read_cache)
    html=(ROOT/'index.html').read_text()
    html=re.sub(r'<script src="([^"]+)"></script>',lambda m:'<script>'+(ROOT/m.group(1)).read_text().replace('</script','<\\/script')+'</script>',html)
    init='window.__CAPTURE__=true;window.__DEFER_CAPTURE_RENDER__=true;window.__SCENE__='+json.dumps(scene)+';window.__LOCAL_MANIFESTS__='+json.dumps({scene:fixed})+';'
    html=html.replace('<head>','<head><script>'+init+'</script>',1)
    page.set_content(html,wait_until='load',timeout=90000)
    page.wait_for_function('window.CYBR?.ready||window.CYBR_ERROR',timeout=90000)
    if page.evaluate('!!window.CYBR_ERROR'):raise RuntimeError(page.evaluate('window.CYBR_ERROR'))
    page.evaluate("CYBR.renderer.setRasterProfile('repair');CYBR.setMode('water')")
    return page

def capture(names,frames=120,chunk=16):
    sources=['src/renderer.js','src/studio.js','index.html','tools/record_repair.py','tools/browser_common.py']
    source_hashes={name:digest(ROOT/name) for name in sources}
    with sync_playwright() as p:
        for scene in names:
            folder=ROOT/'cache'/scene;images=IMAGES/scene;images.mkdir(exist_ok=True)
            for shot in (0,1):(images/str(shot)).mkdir(exist_ok=True)
            report_path=REPORT/f'{scene}.json'
            records=[];retries=[];renderer=None;started=time.time()
            if report_path.exists():
                previous=json.loads(report_path.read_text())
                if previous.get('sourceHashes')==source_hashes:
                    for row in previous['frames']:
                        f=row['frame']
                        if f!=len(records):break
                        if all((images/str(s)/f'{f:04d}.jpg').exists() and digest(images/str(s)/f'{f:04d}.jpg')==row['jpegSha256'][s] for s in (0,1)):
                            records.append(row)
                        else:break
            def report(complete=False,clips=None):
                data={'scene':scene,'complete':complete,'captureResolution':[W,H],'videoFPS':FPS,'physicalPlaybackSpeed':.5,
                    'method':'two cameras on each current simulated state; no interpolation or still-image animation',
                    'boundedBrowserChunkFrames':chunk,'sourceHashes':source_hashes,'frames':records,'renderer':renderer,
                    'javascriptErrors':[],'recoverableCaptureRetries':retries,'wallSecondsThisRun':time.time()-started}
                if clips is not None:data['clips']=clips
                atomic_json(report_path,data)
            while len(records)<frames:
                first=len(records);end=min(frames,first+chunk)
                # Do not hold an idle GPU context while the producer is still running.
                wait_frame(folder,end-1)
                browser=None;errors=[]
                try:
                    browser=launch(p,threads=1);page=open_scene(browser,scene,frames,errors)
                    cdp=page.context.new_cdp_session(page)
                    for frame in range(first,end):
                        _,info,mesh=wait_frame(folder,frame)
                        page.evaluate('([s,f,m])=>{window.__LOCAL_MANIFESTS__[s].frames[f]=m}',[scene,frame,info])
                        check=page.evaluate('(f)=>CYBR.loadFrame(f)',frame)
                        if check['glError'] or check['metrics']['frame']!=frame or not check['metrics']['finite']:raise RuntimeError(check)
                        row={'frame':frame,'physicalTime':info['time'],'particles':info['particles'],'triangles':check['triangles'],
                            'primarySha256':info['primarySha256'],'meshPayloadSha256':mesh['payloadSha256'],'glError':check['glError'],'jpegSha256':[]}
                        for shot in (0,1):
                            page.evaluate('(s)=>CYBR.setShot(s)',shot)
                            image=page.screenshot(type='jpeg',quality=96,animations='disabled',timeout=90000)
                            path=images/str(shot)/f'{frame:04d}.jpg';path.write_bytes(image)
                            row['jpegSha256'].append(hashlib.sha256(image).hexdigest())
                            if frame in (18,32,48,72,96,119):(ROOT/'media'/f'{scene}_{shot}_frame{frame:03d}.jpg').write_bytes(image)
                        if errors:raise RuntimeError('\n'.join(errors))
                        records.append(row);renderer=page.evaluate('CYBR.inspect()');report()
                        if frame%4==0:cdp.send('HeapProfiler.collectGarbage')
                        if frame%12==0:print(json.dumps({'scene':scene,'frame':frame,'elapsed':round(time.time()-started,1)}),flush=True)
                    browser.close();browser=None
                except Exception as exc:
                    retries.append({'frame':len(records),'error':str(exc)[-2500:]});report()
                    if browser:
                        try:browser.close()
                        except Exception:pass
                    print('CAPTURE RETRY',scene,len(records),str(exc)[-160:],flush=True)
                    if len(retries)>5:raise
                    time.sleep(3)
            clips=[]
            for shot,label in ((0,'wide'),(1,'surface')):
                encoder=Encoder(f'{scene}_{label}')
                for frame in range(frames):encoder.add((images/str(shot)/f'{frame:04d}.jpg').read_bytes())
                clips.append(encoder.close())
            report(True,clips)
            print('RECORDED',scene,'frames',frames*2,'wall',round(time.time()-started,1),flush=True)
if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('scenes',nargs='+');a.add_argument('--frames',type=int,default=120);a.add_argument('--chunk',type=int,default=16)
    o=a.parse_args();capture(o.scenes,o.frames,o.chunk)
