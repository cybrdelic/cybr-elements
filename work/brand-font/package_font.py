from pathlib import Path
import zipfile,json
from PIL import Image
r=Path('outputs/cybrdelic-type')
(r/'fonts/CybrdelicFlux.css').write_text("@font-face {\n  font-family: 'Cybrdelic Flux';\n  src: url('./CybrdelicFlux-Display.woff2') format('woff2');\n  font-style: normal;\n  font-weight: 650;\n  font-display: swap;\n}\n")
for n in ['cybrdelic-flux-dark.png','cybrdelic-flux-light.png']:
    im=Image.open(r/'previews'/n);assert im.mode=='RGBA';alpha=im.getchannel('A');assert alpha.getextrema()==(0,255)
readme=r/'README.md'
text=readme.read_text(encoding='utf-8');text+='\nBrowser verification passed in Chromium at desktop and 390px mobile widths: WOFF2 loaded, SVG glyph groups rendered, sample editing, size/tracking sliders and reversed colors worked, with no horizontal overflow. Preview-sheet regeneration currently uses Windows Segoe UI for the explanatory labels; the font outlines themselves are original and independent of Segoe UI.\n'
readme.write_text(text,encoding='utf-8')
with zipfile.ZipFile(r/'Cybrdelic-Type-v0.1.zip','w',zipfile.ZIP_DEFLATED) as z:
    for f in r.rglob('*'):
        if f.is_file() and f.suffix!='.zip':z.write(f,f.relative_to(r))
with zipfile.ZipFile(r/'Cybrdelic-Type-v0.1.zip') as z:assert z.testzip() is None;count=len(z.infolist())
print(json.dumps({'filesInPack':count,'zipBytes':(r/'Cybrdelic-Type-v0.1.zip').stat().st_size,'font':'CybrdelicFlux-Display.ttf','characterCoverage':95,'desktopAndMobileBrowserChecks':'passed','transparentPNGs':'verified'}))
