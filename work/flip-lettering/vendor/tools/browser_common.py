"""Memory-backed, network-free browser capture of the real Three.js build.
No browser policies are changed. JavaScript/cache bytes come from the local build.
Set CHROMIUM_EXECUTABLE to choose a browser, or install Playwright Chromium.
Set CYBR_SOFTWARE_GL=0 to request the normal hardware backend on Linux.
"""
from pathlib import Path
import os,re,json,base64,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
SCENES=['breach','impact','jets','cascade','slosh','vortex','paddle','capillary','viscous','hero','buoy']
def launch(p,threads=2):
    executable=os.environ.get('CHROMIUM_EXECUTABLE') or shutil.which('chromium') or shutil.which('chromium-browser')
    args=['--disable-dev-shm-usage'];env=dict(os.environ)
    if sys.platform.startswith('linux'):
        args.append('--no-sandbox')
        if os.environ.get('CYBR_SOFTWARE_GL','1')=='1':
            args+=['--use-gl=angle','--use-angle=gl-egl','--ignore-gpu-blocklist']
            env.update(EGL_PLATFORM='surfaceless',LIBGL_ALWAYS_SOFTWARE='1',LP_NUM_THREADS=str(threads))
    return p.chromium.launch(executable_path=executable,headless=True,args=args,env=env)
def load(page,scene='breach'):
    manifests={n:json.loads((ROOT/'cache'/n/'manifest.json').read_text()) for n in SCENES if (ROOT/'cache'/n/'manifest.json').exists()}
    def read_cache(name,frame):
        if name not in manifests or not isinstance(frame,int) or not 0<=frame<len(manifests[name]['frames']):
            raise ValueError('Invalid scene or frame requested by capture page')
        return base64.b64encode((ROOT/'cache'/name/f'{frame:04d}.mesh.gz').read_bytes()).decode()
    page.expose_function('__readCache',read_cache)
    html=(ROOT/'index.html').read_text()
    html=re.sub(r'<script src="([^"]+)"></script>',lambda m:'<script>'+ (ROOT/m.group(1)).read_text().replace('</script','<\\/script')+'</script>',html)
    html=html.replace('<head>','<head><script>window.__CAPTURE__=true;window.__SCENE__='+json.dumps(scene)+';window.__LOCAL_MANIFESTS__='+json.dumps(manifests)+';</script>')
    page.set_content(html,wait_until='load',timeout=90000)
    page.wait_for_function('window.CYBR?.ready||window.CYBR_ERROR',timeout=90000)
    if page.evaluate('!!window.CYBR_ERROR'):raise RuntimeError(page.evaluate('window.CYBR_ERROR'))
