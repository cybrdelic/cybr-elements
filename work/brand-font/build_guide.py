from pathlib import Path
import json,zipfile
r=Path('outputs/cybrdelic-type')
html='''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cybrdelic — custom type study</title>
<style>
@font-face{font-family:Flux;src:url('fonts/CybrdelicFlux-Display.woff2') format('woff2');font-style:normal;font-weight:650;font-display:swap}
:root{--paper:#f4f2ed;--ink:#151515;--muted:#686863;--line:#cbc9c1;--acid:#c6f350}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 Arial,sans-serif}a{color:inherit;text-underline-offset:4px}header{padding:24px 5%;display:flex;justify-content:space-between;border-bottom:1px solid var(--line);font-size:12px;letter-spacing:.1em}header span{color:var(--muted)}main{max-width:1500px;margin:auto;padding:0 5%}.eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}.intro{padding:66px 0 34px;display:grid;grid-template-columns:1.4fr 1fr;gap:10%}h1{font:normal clamp(32px,4vw,60px)/1.08 Arial,sans-serif;letter-spacing:-.045em;margin:15px 0 0}p{max-width:610px}.intro p{color:var(--muted);margin-top:36px}.hero{background:#121212;padding:58px 6% 36px;color:var(--paper)}.hero img{display:block;width:100%;height:260px;object-fit:contain}.hero-footer{border-top:1px solid #3a3a38;margin-top:32px;padding-top:22px;display:flex;justify-content:space-between;font-size:12px;letter-spacing:.06em;color:#b5b5ad}section{padding:65px 0;border-bottom:1px solid var(--line)}h2{font-size:26px;font-weight:400;letter-spacing:-.035em;margin:5px 0 24px}.section-top{display:flex;justify-content:space-between;gap:30px;align-items:start}.tag{font-size:11px;padding:7px 10px;border:1px solid var(--ink);white-space:nowrap}.anatomy{display:grid;grid-template-columns:repeat(4,1fr);gap:28px}.anatomy article{border-top:1px solid var(--line)}.glyph{font:650 170px/1.1 Flux;min-height:205px;display:flex;align-items:center}.anatomy h3{font-size:14px;font-weight:400;margin:15px 0 5px}.anatomy p{font-size:13px;color:var(--muted);margin:0}.tester{background:#e9e7df;padding:28px;margin-top:24px}.controls{display:flex;align-items:center;gap:20px;flex-wrap:wrap;font-size:12px;border-bottom:1px solid #bdbbb2;padding-bottom:20px}.controls label{display:flex;align-items:center;gap:10px}.controls button{margin-left:auto;border:1px solid currentColor;padding:9px 16px;background:transparent;color:inherit;cursor:pointer}#sample{font:650 100px/1.2 Flux;letter-spacing:0;min-height:205px;padding:30px 0 15px;overflow-wrap:anywhere;outline:none;caret-color:#63811d}#sample:focus{box-shadow:inset 0 -2px #869850}.tester.dark{background:#151515;color:#f4f2ed}.alphabet{font:650 clamp(23px,4.1vw,56px)/1.8 Flux;overflow-wrap:anywhere;margin-top:26px}.concept{display:grid;grid-template-columns:200px 1fr;gap:40px;align-items:center;padding:28px 0;border-top:1px solid var(--line)}.concept img{width:100%;height:150px;object-fit:contain}.concept p{font-size:13px;color:var(--muted)}.concept h3{font-size:18px;font-weight:400}.rulegrid{display:grid;grid-template-columns:1fr 1fr;gap:40px}.rulegrid p{color:var(--muted);font-size:14px}.downloads{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.downloads a{border:1px solid var(--ink);padding:24px;text-decoration:none}.downloads a:hover{background:var(--acid)}.downloads strong{font-size:19px;font-weight:400;display:block}.downloads small{color:var(--muted)}footer{padding:35px 0 55px;font-size:12px;color:var(--muted)}@media(max-width:700px){header span{display:none}.intro{grid-template-columns:1fr;gap:0;padding-top:35px}.intro p{margin-top:25px}.hero{padding:26px 20px}.hero img{height:150px}.hero-footer{display:block;font-size:10px}.hero-footer span{display:block;margin:5px 0}.anatomy{grid-template-columns:1fr 1fr}.glyph{font-size:130px;min-height:155px}.concept{grid-template-columns:1fr;gap:0}.rulegrid{grid-template-columns:1fr;gap:10px}.downloads{grid-template-columns:1fr}#sample{font-size:64px}.section-top{display:block}.tag{display:inline-block;margin-bottom:20px}.controls button{margin-left:0}}
</style></head><body>
<header><b>CYBRDELIC / TYPE STUDIO</b><span>ORIGINAL LETTERING · VERSION 0.1 · SEPTEMBER 2026</span></header>
<main><div class="intro"><div><div class="eyebrow">Custom brand type</div><h1>A structured body.<br>A liquid instinct.</h1></div><p>Cybrdelic Flux combines broad, almost square bowls with curved returns and cut terminals. Its lowercase rhythm carries the identity before fire, water, texture, or color enters the picture.</p></div>
<div class="hero"><img src="vector/cybrdelic-flux-light.svg" alt="Cybrdelic Flux custom wordmark"><div class="hero-footer"><span>01 / FLUX — RECOMMENDED DIRECTION</span><span>CUSTOM OUTLINES · OPEN COUNTERS · DISPLAY WEIGHT</span></div></div>
<section><div class="section-top"><div><div class="eyebrow">Letterform DNA</div><h2>Four details to build recognition.</h2></div><span class="tag">DRAWN FROM SCRATCH</span></div>
<div class="anatomy"><article><div class="glyph">c</div><h3>01 / The cut</h3><p>A broad bowl ends in two clean diagonal cuts. The opening gives fire and water space to move.</p></article><article><div class="glyph">y</div><h3>02 / The return</h3><p>The upright body drops into a broad leftward hook: the most expressive movement in the name.</p></article><article><div class="glyph">r</div><h3>03 / The shoulder</h3><p>A low, forward-reaching shoulder interrupts the repeated bowls and keeps the middle open.</p></article><article><div class="glyph">i</div><h3>04 / The signal</h3><p>A small tilted lozenge replaces the usual circular dot. Punctuation repeats that shape.</p></article></div></section>
<section><div class="eyebrow">Working font, not a picture</div><h2>Try the lettering.</h2><p>Click the sample to type. The installed-font and browser-font versions use these same outlines and built-in kerning.</p><div class="tester" id="tester"><div class="controls"><label for="size">Size <input type="range" id="size" min="30" max="160" value="100"><output id="sizeValue">100px</output></label><label for="tracking">Tracking <input type="range" id="tracking" min="-3" max="15" value="0"><output id="trackValue">0px</output></label><button type="button" id="reverse" aria-pressed="false">Reverse colors</button></div><div id="sample" contenteditable="true" role="textbox" aria-label="Live Cybrdelic Flux type tester" spellcheck="false">cybrdelic</div></div><div class="alphabet">abcdefghijklmnopqrstuvwxyz<br>ABCDEFGHIJKLMNOPQRSTUVWXYZ<br>0123456789 &amp; @ ! ? % + =</div></section>
<section><div class="eyebrow">Concept exploration</div><h2>Three directions. One name.</h2>
<div class="concept"><div><h3>01 / Flux</h3><p>Recommended. Broad counters and soft returns, interrupted by clipped ends. Best balance for the wordmark and a wider type family.</p></div><img src="vector/01-flux.svg" alt="Flux wordmark concept"></div>
<div class="concept"><div><h3>02 / Undertow</h3><p>A stretched, reverse-leaning variation with a wider c and sweeping y. The more psychedelic option.</p></div><img src="vector/02-undertow.svg" alt="Undertow wordmark concept"></div>
<div class="concept"><div><h3>03 / Relay</h3><p>Condensed strokes and chamfered corners. The more mechanical option. A separate wordmark exploration.</p></div><img src="vector/03-relay.svg" alt="Relay wordmark concept"></div></section>
<section><div class="eyebrow">Use &amp; scope</div><h2>A display prototype for the brand.</h2><div class="rulegrid"><div><p><b>Use the lowercase SVG for the main logo.</b> Its spacing is fixed. Use the font for short headlines, film titles, merchandise, and labels. Keep at least one i-dot width of clear space around the mark; use a 180px minimum wordmark width for this first version.</p><p><b>Work in monochrome first.</b> Ink #151515 and paper #F4F2ED are the base. Signal green #C6F350 is an optional accent for supporting layouts, never required to identify the wordmark.</p></div><div><p><b>95 printable Basic Latin characters.</b> Uppercase, lowercase, numbers, punctuation, and 14 kerning pairs. One display style. Accented languages, multiple weights, and text-size optical tuning are outside this v0.1.</p><p><b>Keep the contours intact.</b> Avoid stretching Flux, adding a heavy outline, or closing the c/e openings. Undertow and Relay are concept alternatives, not approved replacements. For motion, use the named SVG glyph groups as design references; nozzle paths still need a dedicated motion pass.</p></div></div></section>
<section><div class="eyebrow">Files</div><h2>Take the system with you.</h2><div class="downloads"><a href="fonts/CybrdelicFlux-Display.ttf" download><strong>Installable font ↗</strong><small>TTF · Cybrdelic Flux Display</small></a><a href="vector/01-flux.svg" download><strong>Wordmark master ↗</strong><small>SVG · Individually grouped letters</small></a><a href="Cybrdelic-Type-v0.1.zip" download><strong>Complete source pack ↗</strong><small>TTF, WOFF2, SVG, PNG, source &amp; guide</small></a></div></section>
<footer>Original outline construction for Cybrdelic. The recommendation is a design proposal, not a previously approved brand standard. No third-party font outlines were used.</footer></main>
<script>const sample=document.getElementById('sample'),size=document.getElementById('size'),tracking=document.getElementById('tracking');size.addEventListener('input',()=>{sample.style.fontSize=size.value+'px';document.getElementById('sizeValue').value=size.value+'px'});tracking.addEventListener('input',()=>{sample.style.letterSpacing=tracking.value+'px';document.getElementById('trackValue').value=tracking.value+'px'});document.getElementById('reverse').addEventListener('click',function(){let dark=document.getElementById('tester').classList.toggle('dark');this.setAttribute('aria-pressed',String(dark))});sample.addEventListener('paste',e=>{e.preventDefault();document.execCommand('insertText',false,e.clipboardData.getData('text/plain'))});</script>
</body></html>'''
(r/'index.html').write_text(html,encoding='utf-8')
(r/'README.md').write_text('''# Cybrdelic custom type — v0.1

Recommended direction: **Cybrdelic Flux**, an original display font with rounded square bowls, clipped c terminals, a returning y descender, forward r shoulder and lozenge dots. This is a proposed design, not an approved brand standard.

Open `index.html` for the visual guide, three wordmark directions, and a live font tester. Everything runs locally without external fonts or scripts.

## Included

- `fonts/CybrdelicFlux-Display.ttf`: installable desktop font.
- `fonts/CybrdelicFlux-Display.woff2`: compact web font.
- `vector/01-flux.svg`: recommended lowercase logo; each letter has a named group.
- `vector/cybrdelic-flux-light.svg`: light wordmark.
- `vector/02-undertow.svg`, `vector/03-relay.svg`: alternate wordmark studies, not separate full font families.
- `previews/`: concept sheet, alphabet specimen, hero and verified transparent PNGs.
- `source/build_type.py`: reproducible outline/font generator (Python, NumPy, Shapely, fontTools, Brotli, Pillow).
- `source/glyph-outlines.json`: editable contour coordinates, advances and kerning.
- `source/validation.json`: coverage and file checks.

## Coverage and limits

95 printable Basic Latin characters, including A–Z, a–z, figures and punctuation; one display style and 14 selected kerning pairs. No third-party font outlines used. Accents, extended language coverage, additional weights and extensive text-size optical spacing are not included. Use for logos and headlines; use a conventional text face for paragraphs.

## Installation and web use

Double-click the TTF to install through your operating system. The assistant has not installed or registered it automatically.

```css
@font-face {
  font-family: 'Cybrdelic Flux';
  src: url('./fonts/CybrdelicFlux-Display.woff2') format('woff2');
  font-weight: 650;
  font-style: normal;
}
.brand-title { font-family: 'Cybrdelic Flux', sans-serif; font-kerning: normal; }
```

## Use

Use the fixed SVG spacing for the main lowercase wordmark. Start with a 180px minimum logo width and clear space at least one i-dot wide; these are provisional prototype guidelines. Base colors: ink #151515 and paper #F4F2ED; optional supporting accent #C6F350. Do not stretch Flux, close its counters, or add thick strokes. The alternate concepts are intentional separate explorations.

The lettering has not yet been substituted into the fire/water videos. Keep the final font direction separate from the rendering until chosen. SVG outlines are silhouette references, not ready-made single-nozzle trajectories.
''',encoding='utf-8')
# Full development pack excludes the archive itself.
with zipfile.ZipFile(r/'Cybrdelic-Type-v0.1.zip','w',zipfile.ZIP_DEFLATED) as z:
    for f in r.rglob('*'):
        if f.is_file() and f.suffix!='.zip':z.write(f,f.relative_to(r))
print({'guide':str(r/'index.html'),'archiveBytes':(r/'Cybrdelic-Type-v0.1.zip').stat().st_size})
