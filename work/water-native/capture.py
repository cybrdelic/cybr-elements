from pathlib import Path
import json,sys,time
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parent;variant=sys.argv[1];frames=[int(x) for x in sys.argv[2].split(',')];out=R/f'frames-{variant}';out.mkdir(exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1920,'height':1080});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(f'http://127.0.0.1:8767/elements/water/?variant={variant}&capture=1&frame={frames[0]}');page.wait_for_function('window.WATER?.ready || window.WATER_ERROR',timeout=120000)
 assert not page.evaluate('window.WATER_ERROR'),page.evaluate('window.WATER_ERROR')
 for f in frames:
  info=page.evaluate('(f)=>WATER.loadFrame(f)',f);page.screenshot(path=str(out/f'{f:04}.jpg'),type='jpeg',quality=97);assert not info['glError'];print('FRAME',variant,f,flush=True)
 (R/f'capture-{variant}.json').write_text(json.dumps({'frames':frames,'errors':errors,'renderer':page.evaluate('WATER.renderer.info()')}));assert not errors;b.close()
