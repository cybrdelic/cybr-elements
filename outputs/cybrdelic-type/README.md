# Cybrdelic custom type — v0.1

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

Browser verification passed in Chromium at desktop and 390px mobile widths: WOFF2 loaded, SVG glyph groups rendered, sample editing, size/tracking sliders and reversed colors worked, with no horizontal overflow. Preview-sheet regeneration currently uses Windows Segoe UI for the explanatory labels; the font outlines themselves are original and independent of Segoe UI.
