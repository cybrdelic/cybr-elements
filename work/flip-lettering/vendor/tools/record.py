"""Record fresh Three.js frames, never pans over stills or video-frame interpolation.

Every captured frame loads one distinct mesh generated from a distinct solver state.
The live variant steps the identical FLIP module in a browser Worker instead.
Usage: python tools/record.py breach impact
       python tools/record.py --live
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, time
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_common import ROOT, SCENES, launch, load

W,H,FPS=1920,1080,24
OUT=ROOT/'media'/'shots'; OUT.mkdir(parents=True,exist_ok=True)
REPORT=ROOT/'tests'/'captures';REPORT.mkdir(parents=True,exist_ok=True)

class Encoder:
    def __init__(self,name:str):
        self.path=OUT/f'{name}_1080p.mp4'
        self.errorfile=open(OUT/f'{name}.ffmpeg.log','wb')
        self.proc=subprocess.Popen([
            'ffmpeg','-hide_banner','-loglevel','error','-y',
            '-f','image2pipe','-vcodec','mjpeg','-framerate',str(FPS),'-i','pipe:0',
            '-an','-vf','scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p,sidedata=delete,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709','-color_range','tv','-c:v','libx264','-preset','fast','-tune','zerolatency','-bf','0','-rc-lookahead','0','-crf','17','-threads','1',
            '-pix_fmt','yuv420p','-color_primaries','bt709','-color_trc','bt709',
            '-colorspace','bt709','-movflags','+faststart',str(self.path)
        ],stdin=subprocess.PIPE,stderr=self.errorfile)
        self.hashes=[]
    def add(self,b:bytes):
        assert self.proc.stdin is not None
        self.proc.stdin.write(b)
        self.hashes.append(hashlib.sha256(b).hexdigest())
    def close(self):
        if self.proc.stdin and not self.proc.stdin.closed:self.proc.stdin.close()
        code=self.proc.wait(timeout=90);self.errorfile.close()
        if code:raise RuntimeError(f'Encoder failed ({code}): {self.path}')
        return {'path':str(self.path.relative_to(ROOT)), 'capturedFrames':len(self.hashes),
                'uniqueJpegFrames':len(set(self.hashes)),'jpegSha256':self.hashes}

def record_cached(names:list[str]):
    with sync_playwright() as p:
        b=launch(p,threads=2)
        page=b.new_page(viewport={'width':W,'height':H},device_scale_factor=1)
        page.set_default_timeout(600000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
        load(page,names[0]);page.evaluate("window.__DEFER_CAPTURE_RENDER__=true;CYBR.renderer.opticsMode='raster'");cdp=page.context.new_cdp_session(page)
        for scene in names:
            if page.evaluate('CYBR.inspect().scene')!=scene:
                page.evaluate('(s)=>CYBR.selectCache(s)',scene)
            page.evaluate("CYBR.setMode('water')")
            manifest=json.loads((ROOT/'cache'/scene/'manifest.json').read_text())
            encoders=[Encoder(f'{scene}_wide'),Encoder(f'{scene}_surface')]
            records=[];started=time.time()
            for f in range(len(manifest['frames'])):
                info=page.evaluate('(f)=>CYBR.loadFrame(f)',f)
                if info['glError']!=0:raise RuntimeError(f'WebGL error {info}')
                if info['metrics']['frame']!=f:raise RuntimeError('Unexpected simulation frame')
                records.append({'frame':f,'simulationTime':info['metrics']['time'],
                    'vertices':info['vertices'],'triangles':info['triangles'],
                    'particles':info['metrics']['particles'],'glError':info['glError']})
                for shot,encoder in enumerate(encoders):
                    page.evaluate('(s)=>CYBR.setShot(s)',shot)
                    image=page.screenshot(type='jpeg',quality=95,animations='disabled')
                    encoder.add(image)
                    if f in (18,42,66,94):
                        (ROOT/'media'/f'{scene}_{shot}_frame{f:03d}.jpg').write_bytes(image)
                if f%12==0:
                    cdp.send('HeapProfiler.collectGarbage')
                    print(json.dumps({'scene':scene,'frame':f,'elapsed':round(time.time()-started,1)}),flush=True)
            clips=[e.close() for e in encoders]
            info=page.evaluate('CYBR.inspect()')
            result={'scene':scene,'kind':'simulated-mesh playback','renderer':info,
                    'sourceResolution':[W,H],'videoFPS':FPS,'simulationDt':manifest['frameDt'],
                    'playbackSpeed':FPS*manifest['frameDt'],'frames':records,'clips':clips,
                    'javascriptErrors':errors[:],'wallSeconds':time.time()-started}
            (REPORT/f'{scene}.json').write_text(json.dumps(result,indent=2))
            print('FINISHED',scene,'seconds',round(time.time()-started,1),flush=True)
        b.close()

def record_diagnostics():
    with sync_playwright() as p:
        b=launch(p,threads=2);page=b.new_page(viewport={'width':W,'height':H},device_scale_factor=1)
        page.set_default_timeout(600000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        load(page,'breach');clips=[];records=[];started=time.time();cdp=page.context.new_cdp_session(page)
        modes=[('breach','particles','diagnostic_particles'),('breach','normal','diagnostic_normals'),('jets','whitewater','diagnostic_whitewater'),('impact','thickness','diagnostic_thickness')]
        for scene,mode,name in modes:
            if page.evaluate('CYBR.inspect().scene')!=scene:page.evaluate('(s)=>CYBR.selectCache(s)',scene)
            page.evaluate('(m)=>CYBR.setMode(m)',mode);page.evaluate('CYBR.setShot(0)');encoder=Encoder(name)
            for i in range(48):
                f=i+24;info=page.evaluate('(f)=>CYBR.loadFrame(f)',f)
                if info['glError']:raise RuntimeError(info)
                encoder.add(page.screenshot(type='jpeg',quality=95,animations='disabled'))
                records.append({'scene':scene,'mode':mode,'frame':f,'time':info['metrics']['time']})
                if i==24:page.screenshot(path=str(ROOT/'media'/f'{name}.png'))
                if i%12==0:cdp.send('HeapProfiler.collectGarbage');print('DIAGNOSTIC',mode,f,flush=True)
            clips.append(encoder.close())
        result={'kind':'diagnostic simulated geometry','clips':clips,'frames':records,
                'renderer':page.evaluate('CYBR.inspect()'),'javascriptErrors':errors,'wallSeconds':time.time()-started}
        (REPORT/'diagnostics.json').write_text(json.dumps(result,indent=2));b.close()

def record_live():
    with sync_playwright() as p:
        b=launch(p,threads=2);page=b.new_page(viewport={'width':W,'height':H},device_scale_factor=1)
        page.set_default_timeout(600000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        html=(ROOT/'standalone.html').read_text().replace('<head>','<head><script>window.__CAPTURE__=true;window.__CAPTURE_LIVE__=true;</script>',1)
        page.set_content(html,wait_until='load',timeout=90000)
        page.wait_for_function('window.CYBR?.ready||window.CYBR_ERROR',timeout=90000)
        if page.evaluate('!!window.CYBR_ERROR'):raise RuntimeError(page.evaluate('window.CYBR_ERROR'))
        if page.evaluate('CYBR.config===null'):raise RuntimeError('Missing live solver configuration')
        page.evaluate('CYBR.setShot(0)');encoder=Encoder('live_worker_proof');records=[];started=time.time()
        for f in range(96):
            if f:page.evaluate('CYBR.stepLive(1/48)')
            info=page.evaluate('CYBR.inspect()')
            if info['glError'] or not info['metrics']['finite']:raise RuntimeError(info)
            if f==48:page.evaluate("CYBR.setMode('particles')")
            encoder.add(page.screenshot(type='jpeg',quality=95,animations='disabled'))
            records.append(info)
            if f%12==0:print('LIVE FRAME',f,'t',info['metrics']['time'],'wall',round(time.time()-started,1),flush=True)
        clip=encoder.close();result={'kind':'live browser Worker, solver stepped once for every rendered frame',
            'frames':records,'clips':[clip],'javascriptErrors':errors,'wallSeconds':time.time()-started}
        (REPORT/'live.json').write_text(json.dumps(result,indent=2));b.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('scenes',nargs='*');parser.add_argument('--live',action='store_true');parser.add_argument('--diagnostics',action='store_true');args=parser.parse_args()
    if any(s not in SCENES for s in args.scenes):parser.error('Unknown scene. Choose: '+', '.join(SCENES))
    if args.live:record_live()
    elif args.diagnostics:record_diagnostics()
    else:record_cached(args.scenes or SCENES)
