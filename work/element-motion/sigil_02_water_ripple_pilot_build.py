from pathlib import Path
r=Path(__file__).resolve().parent;s=(r/'sigil_02_water_hold_render.py').read_text()
s=s.replace("out=R/('sigil-02-water-hold/frames' if '--full' in sys.argv else 'sigil-02-water-hold/pilot')", "out=R/'sigil-02-water-hold/ripple-pilot'")
s=s.replace("frames=range(300) if '--full' in args else [45,75,120,165]", "frames=[120,165]")
(r/'sigil_02_water_ripple_pilot_render.py').write_text(s)
print('CPU capillary-normal pilot ready')
